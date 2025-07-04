# data.knowportland.org

## Set up and Usage

## Usage

The follow instructions are for a mac and use brew. Please adjust as needed for your system.

TODO: add instructions for setting up .env

```
# 0. Install
# Install poppler for pdftotext
brew install poppler

# Install astral and install python dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

Then run it

```
python knowportland.py crawl

# 3. Outputs text files. Puts them into data/portland_minutes_texts
cd data/portland_minutes_pdfs
for file in *.pdf; do pdftotext "$file" "${file%.pdf}.txt"; done
mv *.txt ../portland_minutes_texts

# 4. Chunk the text files. Puts them into data/portland_minutes_chunks
python make_chunks.py

# 5. Build sqlite database
# 5a. Embed the chunks into an llm collection in data/portland.db
llm embed-multi pdx \
 --model sentence-transformers/all-MiniLM-L6-v2 \
 --store \
 --database data/portland.db \
 --files data/portland_minutes_chunks '*.txt'

# 5b. Import the files table
sqlite-utils insert data/portland.db files data/portland_minutes_pdfs/metadata.json --pk file_id

# 5c. Add meeting_id to embeddings
sqlite-utils add-column data/portland.db embeddings file_id text
sqlite-utils query data/portland.db "update embeddings set file_id = id"
sqlite-utils convert data/portland.db embeddings file_id 'value.split("_")[0] if "_" in value else value' --import sqlite_utils
sqlite-utils add-foreign-key data/portland.db embeddings file_id files file_id

# 6. Start datasette
datasette data/portland.db

# 7. query
# Query with datasette as a tool:
python query.py \
  --prompt "Which city councilors spoke in a meeting with id 17141131?"

# Query with RAG (direct to sqlite file, not datasette):
python query.py \
  --rag \
  --prompt "Which city councilors spoke in an embedding with id 17141131_chunk_006.txt?"
```

## Development

```
# To run checks
uv run ruff check

# To add a dependency
uv add ruff
```
