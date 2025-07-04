import click
import sqlite_utils
import llm
import dotenv
import os
import tiktoken
from llm_tools_datasette import Datasette
import os
import json
import time
import logging
import requests
import subprocess
from bs4 import BeautifulSoup
from urllib.parse import urljoin

dotenv.load_dotenv()
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Chunking configuration
CHUNK_SIZE = 5000
OVERLAP = 250
MODEL = "gpt-3.5-turbo"
INPUT_DIR = "data/portland_minutes_texts"
OUTPUT_DIR = "data/portland_minutes_chunks"


class PortlandMinutesScraper:
    def __init__(self, outdir: str):
        self.base_url = "https://efiles.portlandoregon.gov"

        # We have ?pageSize and ?start for pagination
        self.start_url = (
            "https://efiles.portlandoregon.gov/record?"
            "q=recContainer:17141116&sortBy=recCreatedOn&pageSize=1000&start=0"
        )

        self.outdir = outdir
        os.makedirs(self.outdir, exist_ok=True)

    def _fetch_html(self, url: str) -> str:
        response = requests.get(url)
        response.raise_for_status()
        return response.text

    def _save_file(self, pdf_url: str, filename: str) -> None:
        """Used for saving a pdf or another file type"""
        response = requests.get(pdf_url)
        response.raise_for_status()
        with open(filename, "wb") as f:
            f.write(response.content)

    def _extract_pdf_url(self, soup) -> str | None:
        try:
            iframe_link = soup.find_all("iframe")[1]["src"]
        except (IndexError, KeyError):
            logger.warning(f"No valid iframe found")
            return None

        iframe_url = urljoin(self.base_url, iframe_link)
        iframe_response = requests.get(iframe_url)
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

    def scrape_all(self):
        # The start url is basically the list of meetings (paginated)
        # Pagination isn't handled yet
        html = self._fetch_html(self.start_url)
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
        print(f"Found {len(a_tags)} meeting links.")

        data = []
        for i, a_tag in enumerate(a_tags):
            meeting_page_url = urljoin(self.base_url, a_tag["href"]).rstrip("/")
            meeting_id = meeting_page_url.rstrip("/").split("/")[-1]
            logger.info("Processing %s / %s: %s", i, len(a_tags), meeting_page_url)

            meeting_soup = BeautifulSoup(
                self._fetch_html(meeting_page_url), "html.parser"
            )
            title = meeting_soup.find("h2").get_text(strip=True)
            logger.info("Processing meeting: %s", title)

            pdf_url = self._extract_pdf_url(meeting_soup)
            if not pdf_url:
                continue

            file_id = pdf_url.rstrip("/").split("/")[-3]
            filename = os.path.join(self.outdir, f"{file_id}.pdf")
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
        with open(os.path.join(self.outdir, "metadata.json"), "w") as f:
            json.dump(data, f, indent=4)

    def transcribe_pdfs(self):
        """Convert PDFs to text files."""
        logger.info("Converting PDFs to text files...")
        pdf_dir = self.outdir

        try:
            # Convert all PDFs to text
            for file in os.listdir(pdf_dir):
                if file.endswith(".pdf"):
                    pdf_path = os.path.join(pdf_dir, file)
                    txt_file = f"{file[:-4]}.txt"
                    txt_path = os.path.join(pdf_dir, txt_file)
                    subprocess.run(["pdftotext", pdf_path, txt_path], check=True)
                    logger.info(f"Converted {pdf_path} to {txt_path}")

            # Move all text files to the texts directory
            texts_dir = os.path.join(os.path.dirname(pdf_dir), "portland_minutes_texts")
            for file in os.listdir(pdf_dir):
                if file.endswith(".txt"):
                    src_path = os.path.join(pdf_dir, file)
                    dst_path = os.path.join(texts_dir, file)
                    subprocess.run(["mv", src_path, dst_path], check=True)
                    logger.info(f"Moved {src_path} to {dst_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error during PDF conversion: {e}")

        logger.info("PDF to text conversion completed.")


@click.help_option("-h", "--help")
@click.group()
def cli():
    """Know Portland - A tool for querying Portland city data and processing text chunks."""
    pass


@cli.command()
@click.option("-p", "--prompt", required=True, help="Prompt to ask the model")
@click.option("--rag", is_flag=True, help="Use RAG mode")
def query(prompt: str, rag: bool):
    """Query the Portland data using either RAG or tool mode."""
    if rag:
        rag_mode(prompt)
    else:
        tool_mode(prompt)


@cli.command()
@click.option("--chunk-size", default=CHUNK_SIZE, help="Size of each chunk in tokens")
@click.option("--overlap", default=OVERLAP, help="Overlap between chunks in tokens")
@click.option("--model", default=MODEL, help="Model to use for tokenization")
@click.option(
    "--input-dir", default=INPUT_DIR, help="Input directory containing text files"
)
@click.option("--output-dir", default=OUTPUT_DIR, help="Output directory for chunks")
def chunk(chunk_size: int, overlap: int, model: str, input_dir: str, output_dir: str):
    """Process text files into chunks for RAG processing."""
    process_chunks(chunk_size, overlap, model, input_dir, output_dir)


@cli.command()
def crawl():
    """Crawl Portland city meeting minutes and download PDFs."""
    # TODO: abstract out the directory names or basename

    os.makedirs("data/", exist_ok=True)
    os.makedirs("data/portland_minutes_pdfs", exist_ok=True)
    os.makedirs("data/portland_minutes_texts", exist_ok=True)
    os.makedirs("data/portland_minutes_chunks", exist_ok=True)
    output_dir = "data/portland_minutes_pdfs"
    scraper = PortlandMinutesScraper(output_dir)
    scraper.scrape_all()


def rag_mode(prompt: str):
    """RAG version"""
    db = sqlite_utils.Database("data/portland.db")
    collection = llm.Collection("pdx", db=db)

    similar_resp = collection.similar(prompt, number=5)

    full_prompt = ""
    for item in similar_resp:
        full_prompt += "<minutes>{}</minutes>\n".format(item.content)
    full_prompt += "\n\nUsing the minutes above, answer the following: {}".format(
        prompt
    )

    model = llm.get_model("gpt-4o-mini")
    response = model.prompt(full_prompt, key=OPENAI_API_KEY)
    print(response.text())


def tool_mode(prompt: str):
    """Tool mode using Datasette"""
    model = llm.get_model("gpt-4o-mini")
    response = model.chain(
        prompt, key=OPENAI_API_KEY, tools=[Datasette("http://localhost:8001/portland")]
    )
    print(response.text())


def chunk_tokens(tokens, size, overlap):
    """Split tokens into chunks with overlap."""
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + size
        chunks.append(tokens[start:end])
        start += size - overlap
    return chunks


def process_chunks(
    chunk_size: int, overlap: int, model: str, input_dir: str, output_dir: str
):
    """Process text files into chunks."""
    # Setup tokenizer
    encoding = tiktoken.encoding_for_model(model)
    os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(input_dir):
        if filename.endswith(".txt"):
            filepath = os.path.join(input_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()

            tokens = encoding.encode(text)
            token_chunks = chunk_tokens(tokens, chunk_size, overlap)

            base = os.path.splitext(filename)[0]
            for i, chunk in enumerate(token_chunks):
                chunk_text = encoding.decode(chunk)
                out_path = os.path.join(output_dir, f"{base}_chunk_{i:03}.txt")
                with open(out_path, "w", encoding="utf-8") as out_file:
                    out_file.write(chunk_text)

            print(f"Processed {filename}: {len(token_chunks)} chunks")
    print("✅ All files processed.")


if __name__ == "__main__":
    cli()
