# data.knowportland.org

- Datasette is on fly at: https://data-knowportland.fly.dev/

## Deployment

After building the database, deploy to fly:

```bash
$ datasette publish fly data/portland.db --app="data-knowportland"
```

This deploys to the URL: https://data-knowportland.fly.dev/.

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
python knowportland.py build

# After building the db, run these

llm embed-multi pdx \
 --model sentence-transformers/all-MiniLM-L6-v2 \
 --store \
 --database data/portland.db \
 --files data/portland_minutes_chunks '*.txt'
sqlite-utils insert data/portland.db files data/portland_minutes_pdfs/metadata.json --pk file_id
sqlite-utils add-column data/portland.db embeddings file_id text
sqlite-utils query data/portland.db "update embeddings set file_id = id"
sqlite-utils convert data/portland.db embeddings file_id 'value.split("_")[0] if "_" in value else value' --import sqlite_utils
sqlite-utils add-foreign-key data/portland.db embeddings file_id files file_id

# 6. Start datasette
datasette data/portland.db

# 7. query
# Query with datasette as a tool:
python knowportland.py query \
  --prompt "Which city councilors were in attendence in a meeting with id 17141131? The files table has a meeting_id column."

# Query with RAG (direct to sqlite file, not datasette):
python knowportland.py query --rag \
  --prompt "Which city councilors spoke in an embedding with id 17141131_chunk_006.txt?"
```

## Development

```
# To run checks
uv run ruff check

# To add a dependency
uv add ruff
```
