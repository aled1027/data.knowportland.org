# data.knowportland.org

## Usage

```
# 0. setup
mkdir -p data/
mkdir -p data/portland_minutes_pdfs
mkdir -p data/portland_minutes_texts
mkdir -p data/portland_minutes_chunks

# 1. Crawl to download pdfs. Puts them into data/portland_minutes_pdfs
python crawl.py

# 2. Outputs text files. Puts them into data/portland_minutes_texts
cd data/portland_minutes_pdfs
for file in *.pdf; do pdftotext "$file" "${file%.pdf}.txt"; done
mv *.txt ../portland_minutes_texts

# 3. Chunk the text files. Puts them into data/portland_minutes_chunks
python make_chunks.py

# 4. Build sqlite database
# 4a. Embed the chunks into an llm collection in data/portland.db
llm embed-multi pdx \
 --model sentence-transformers/all-MiniLM-L6-v2 \
 --store \
 --database data/portland.db \
 --files data/portland_minutes_chunks '*.txt'

# 4b. Import the files table
sqlite-utils insert data/portland.db files data/portland_minutes_pdfs/metadata.json --pk file_id

# 4c. Add meeting_id to embeddings
sqlite-utils add-column data/portland.db embeddings file_id text
sqlite-utils query data/portland.db "update embeddings set file_id = id"
sqlite-utils convert data/portland.db embeddings file_id 'value.split("_")[0] if "_" in value else value' --import sqlite_utils
sqlite-utils add-foreign-key data/portland.db embeddings file_id files file_id

# 5. Start datasette
datasette data/portland.db

# 6. query
# Query with datasette as a tool:
python alex_api/knowportland/utils/query.py \
  --prompt "Which city councilors spoke in a meeting with id 17141131?"

# Query with RAG (direct to sqlite file, not datasette):
python alex_api/knowportland/utils/query.py \
  --rag \
  --prompt "Which city councilors spoke in an embedding with id 17141131_chunk_006.txt?"
```

## UV Tips

```bash
uv add ruff
uv run ruff check
```
