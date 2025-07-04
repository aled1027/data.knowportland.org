import os
import tiktoken

# Configuration
CHUNK_SIZE = 5000
OVERLAP = 250
MODEL = "gpt-3.5-turbo"
INPUT_DIR = "data/portland_minutes_texts"  # current directory
OUTPUT_DIR = "data/portland_minutes_chunks"  # output directory for chunks

# Setup tokenizer
encoding = tiktoken.encoding_for_model(MODEL)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def chunk_tokens(tokens, size, overlap):
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + size
        chunks.append(tokens[start:end])
        start += size - overlap
    return chunks


def go():
    for filename in os.listdir(INPUT_DIR):
        if filename.endswith(".txt"):
            filepath = os.path.join(INPUT_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()

            tokens = encoding.encode(text)
            token_chunks = chunk_tokens(tokens, CHUNK_SIZE, OVERLAP)

            base = os.path.splitext(filename)[0]
            for i, chunk in enumerate(token_chunks):
                chunk_text = encoding.decode(chunk)
                out_path = os.path.join(OUTPUT_DIR, f"{base}_chunk_{i:03}.txt")
                with open(out_path, "w", encoding="utf-8") as out_file:
                    out_file.write(chunk_text)

            print(f"Processed {filename}: {len(token_chunks)} chunks")
    print("✅ All files processed.")


if __name__ == "__main__":
    go()
