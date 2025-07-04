import json
import logging
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urljoin

import click
import dotenv
import httpx
import llm
import sqlite_utils
import tiktoken
from bs4 import BeautifulSoup
from llm_tools_datasette import Datasette

dotenv.load_dotenv()
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PortlandDBBuilder:
    def __init__(self):
        self.base_url = "https://efiles.portlandoregon.gov"
        self.chunk_size = 5000
        self.chunk_token_overlap = 250
        self.chunk_model = "gpt-3.5-turbo"
        # We have ?pageSize and ?start for pagination
        self.scrape_start_url = (
            "https://efiles.portlandoregon.gov/record?"
            "q=recContainer:17141116&sortBy=recCreatedOn&pageSize=1000&start=0"
        )

        self.httpx_client = httpx.Client(
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )

        self.base_dir = "data"
        self.metadata_filepath = os.path.join(self.base_dir, "metadata.json")
        self.file_dir = os.path.join(self.base_dir, "portland_minutes_pdfs")
        self.text_dir = os.path.join(self.base_dir, "portland_minutes_texts")
        self.chunk_dir = os.path.join(self.base_dir, "portland_minutes_chunks")

        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.file_dir, exist_ok=True)
        os.makedirs(self.text_dir, exist_ok=True)
        os.makedirs(self.chunk_dir, exist_ok=True)

    def _fetch_html(self, url: str) -> str:
        response = self.httpx_client.get(url)
        response.raise_for_status()
        return response.text

    def _save_file(self, pdf_url: str, filename: str) -> None:
        """Used for saving a pdf or another file type"""
        response = self.httpx_client.get(pdf_url)
        response.raise_for_status()
        with open(filename, "wb") as f:
            f.write(response.content)

    def _extract_pdf_url(self, soup) -> str | None:
        try:
            iframe_link = soup.find_all("iframe")[1]["src"]
        except (IndexError, KeyError):
            logger.warning("No valid iframe found")
            return None

        iframe_url = urljoin(self.base_url, iframe_link)
        iframe_response = self.httpx_client.get(iframe_url)
        iframe_response.raise_for_status()

        iframe_soup = BeautifulSoup(iframe_response.text, "html.parser")
        pdf_links = [
            a
            for a in iframe_soup.find_all("a", title="Download File")
            if a.get_text(strip=True).lower() == "pdf" and "href" in a.attrs
        ]

        if not pdf_links:
            logger.warning(f"No PDF link found on {iframe_url}")
            return None

        return urljoin(self.base_url, pdf_links[0]["href"])

    def scrape_files(self):
        """Scrape the files from the start url.

        The start url is basically the list of meetings (paginated)
        Pagination isn't handled yet
        """
        html = self._fetch_html(self.scrape_start_url)
        soup = BeautifulSoup(html, "html.parser")

        def is_good_tag(tag):
            # Check if the tag is an <a> tag with "href" and contains "minutes"
            return (
                tag.name == "a"
                and "href" in tag.attrs
                and "minutes" in tag.get_text(strip=True).lower()
            )

        a_tags = soup.find_all("a", href=True)
        a_tags = [a for a in a_tags if is_good_tag(a)]
        logger.info(f"Found {len(a_tags)} meeting links.")

        data = []
        for i, a_tag in enumerate(a_tags):
            meeting_page_url = urljoin(self.base_url, a_tag["href"]).rstrip("/")
            meeting_id = meeting_page_url.rstrip("/").split("/")[-1]
            logger.info("Processing %s / %s: %s", i, len(a_tags), meeting_page_url)

            meeting_soup = BeautifulSoup(
                self._fetch_html(meeting_page_url),
                "html.parser",
            )
            title = meeting_soup.find("h2").get_text(strip=True)
            logger.info("Processing meeting: %s", title)

            pdf_url = self._extract_pdf_url(meeting_soup)
            if not pdf_url:
                continue

            file_id = pdf_url.rstrip("/").split("/")[-3]
            filename = os.path.join(self.file_dir, f"{file_id}.pdf")
            self._save_file(pdf_url, filename)

            metadata = {
                "file_id": file_id,
                "meeting_id": meeting_id,
                "pdf_url": pdf_url,
                "meeting_page_url": meeting_page_url,
                "filename": filename,
                "title": title,
            }
            data.append(metadata)
            time.sleep(1)

        # Write data to a file
        with open(self.metadata_filepath, "w") as f:
            json.dump(data, f, indent=4)

    def transcribe_pdfs(self):
        """Convert PDFs to text files."""
        logger.info("Converting PDFs to text files...")
        pdf_dir = Path(self.file_dir)
        text_dir = Path(self.text_dir)

        try:
            # Convert all PDFs to text
            for pdf_file in pdf_dir.glob("*.pdf"):
                txt_file = text_dir / f"{pdf_file.stem}.txt"

                # Skip if text file already exists
                if txt_file.exists():
                    logger.info(f"Skipping already converted: {pdf_file.name}")
                    continue

                try:
                    subprocess.run(
                        ["pdftotext", str(pdf_file), str(txt_file)],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    logger.info(f"Converted {pdf_file.name} to {txt_file.name}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to convert {pdf_file.name}: {e.stderr}")
                    # Remove partial file if it exists
                    if txt_file.exists():
                        txt_file.unlink()

        except Exception as e:
            logger.error(f"Error during PDF conversion: {e}")

        logger.info("PDF to text conversion completed.")

    def chunk_tokens(self, tokens, size, overlap):
        """Split tokens into chunks with overlap."""
        chunks = []
        start = 0
        while start < len(tokens):
            end = start + size
            chunks.append(tokens[start:end])
            start += size - overlap
        return chunks

    def process_chunks(self):
        """Process text files into chunks."""
        encoding = tiktoken.encoding_for_model(self.chunk_model)
        os.makedirs(self.chunk_dir, exist_ok=True)

        for filename in os.listdir(self.text_dir):
            if filename.endswith(".txt"):
                filepath = os.path.join(self.text_dir, filename)
                with open(filepath, encoding="utf-8") as f:
                    text = f.read()

                tokens = encoding.encode(text)
                token_chunks = self.chunk_tokens(
                    tokens,
                    self.chunk_size,
                    self.chunk_token_overlap,
                )

                base = os.path.splitext(filename)[0]
                for i, chunk in enumerate(token_chunks):
                    chunk_text = encoding.decode(chunk)
                    out_path = os.path.join(self.chunk_dir, f"{base}_chunk_{i:03}.txt")
                    with open(out_path, "w", encoding="utf-8") as out_file:
                        out_file.write(chunk_text)

                logger.info(f"Processed {filename}: {len(token_chunks)} chunks")
        logger.info("✅ All files processed.")

    def actually_build_db(self):
        """Actually build the database."""
        logger.info("Starting database post-processing...")

        # Initialize database
        db = sqlite_utils.Database("data/portland.db")

        # Create embeddings using llm embed-multi
        subprocess.run(
            [
                "llm",
                "embed-multi",
                "pdx",
                "--model",
                "sentence-transformers/all-MiniLM-L6-v2",
                "--store",
                "--database",
                "data/portland.db",
                "--files",
                "data/portland_minutes_chunks",
                "*.txt",
            ],
            check=True,
        )

        # Create the files table based on the metadata file
        with open(self.metadata_filepath, "r") as f:
            files_data = json.load(f)

        files_table = db["files"]
        files_table.insert_all(files_data, pk="file_id", replace=True)

        def extract_base_filename(value):
            # Helper function for extracting the base filename from the file_id
            # in the embeddings table
            return value.split("_")[0] if "_" in value else value

        db["embeddings"].add_column("file_id", str)
        db.execute("UPDATE embeddings SET file_id = id")
        db["embeddings"].convert("file_id", extract_base_filename)
        db["embeddings"].add_foreign_key("file_id", "files", "file_id")


class DatabaseQuerier:
    def __init__(self, local: bool):
        llm_model_name = "gpt-4o-mini"
        self.llm_model = llm.get_model(llm_model_name)
        self.use_local = local

        if self.use_local:
            self.datasette_url = "http://localhost:8001/portland"
        else:
            self.datasette_url = "https://data.knowportland.org/portland"

    def query_with_llm(self, prompt: str) -> str:
        """Tool mode using Datasette"""
        response = self.llm_model.chain(
            prompt,
            key=OPENAI_API_KEY,
            tools=[Datasette(self.datasette_url)],
        )
        return response.text()

    def query_with_rag(self, prompt: str) -> str:
        """RAG version"""
        db = sqlite_utils.Database("data/portland.db")
        collection = llm.Collection("pdx", db=db)
        similar_resp = collection.similar(prompt, number=5)

        full_prompt = ""
        for item in similar_resp:
            full_prompt += f"<minutes>{item.content}</minutes>\n"
        full_prompt += f"\n\nUsing the minutes above, answer the following: {prompt}"

        response = self.llm_model.prompt(full_prompt, key=OPENAI_API_KEY)
        return response.text()


@click.help_option("-h", "--help")
@click.group()
def cli():
    """Know Portland - A tool for querying Portland city data
    and processing text chunks."""
    pass


@cli.command()
def build():
    """Build the Portland city meeting minutes database."""
    scraper = PortlandDBBuilder()
    # scraper.scrape_files()
    # scraper.transcribe_pdfs()
    # scraper.process_chunks()
    scraper.actually_build_db()


@cli.command()
@click.option("-p", "--prompt", required=True, help="Prompt to ask the model")
@click.option("--rag", is_flag=True, help="Use RAG mode")
@click.option("--local", is_flag=True, help="Use local datasette")
def query(prompt: str, rag: bool, local: bool):
    """Query the Portland data using either RAG or tool mode."""
    querier = DatabaseQuerier(local)
    if rag:
        response = querier.query_with_rag(prompt)
    else:
        response = querier.query_with_llm(prompt)
    print(response)


if __name__ == "__main__":
    cli()
