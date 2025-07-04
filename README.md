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

# If running with --local, then start datasette
datasette data/portland.db

# Query with datasette as a tool:

# Quick good tests for whether the tools is working:
python knowportland.py query --prompt "What is the pk of the embedding table?" --local
python knowportland.py query --prompt "What is the pk of the embedding table?"


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
