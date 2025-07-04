import click
import sqlite_utils
import llm
import dotenv
import os
import tiktoken
from llm_tools_datasette import Datasette

dotenv.load_dotenv()
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# Chunking configuration
CHUNK_SIZE = 5000
OVERLAP = 250
MODEL = "gpt-3.5-turbo"
INPUT_DIR = "data/portland_minutes_texts"
OUTPUT_DIR = "data/portland_minutes_chunks"


@click.group()
@click.help_option("-h", "--help")
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
