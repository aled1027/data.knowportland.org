# Data KnowPortland

A data pipeline and query interface for Portland city data. This project scrapes, processes, and makes searchable Portland's public meeting records using AI-powered natural language queries.

## 🚀 Live Demo

- **Datasette Interface**: https://data.knowportland.org
- **Source Data**: Portland eFiles system

## 📋 Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Development](#development)
- [Deployment](#deployment)
- [Contributing](#contributing)

## ✨ Features

- **Web Scraping**: Automatically downloads Portland city council meeting PDFs
- **Text Processing**: Converts PDFs to searchable text with intelligent chunking
- **AI-Powered Queries**: Natural language interface to query meeting data
- **RAG Integration**: Retrieval-Augmented Generation for context-aware responses
- **Datasette Interface**: Web-based SQL query interface with full-text search

## 🔧 Prerequisites

- Python 3.12 or higher
- macOS (instructions provided for Homebrew)
- OpenAI API key (required for AI queries)

## 📦 Installation

### 1. Install System Dependencies

```bash
# Install poppler for PDF text extraction
brew install poppler
```

### 2. Install Python Dependencies

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

### 3. Environment Setup

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=your_openai_api_key_here
```

## 🚀 Usage

### Build the Database

First, scrape and process the Portland meeting data:

```bash
python knowportland.py build
```

This will:

- Scrape meeting PDFs from Portland's eFiles system
- Convert PDFs to text
- Create searchable chunks
- Build a SQLite database with embeddings

### Query the Data

#### Using the Local Datasette Interface

```bash
# Start the local Datasette server
datasette data/portland.db
```

Then visit `http://localhost:8001` in your browser.

#### Using AI-Powered Queries

Test the system with simple queries:

```bash
# Test basic functionality (requires local datasette to be running)
python knowportland.py query --prompt "What is the primary key of the embedding table?" --local

# Query without local mode (uses deployed instance)
python knowportland.py query --prompt "What is the primary key of the embedding table?"
```

**Note**: When using `--local` mode, make sure the local Datasette server is running (`datasette data/portland.db`).

#### Advanced Queries

```bash
# Query specific meeting attendance
python knowportland.py query \
  --prompt "Which city councilors were in attendance at meeting ID 17141131?"

# Use RAG for context-aware responses
python knowportland.py query --rag \
  --prompt "Which city councilors spoke in chunk 17141131_chunk_006.txt?"
```

## 🛠️ Development

### Code Quality

```bash
# Run linting checks
uv run ruff check

# Format code
uv run ruff format
```

### Adding Dependencies

```bash
# Add a new dependency
uv add package_name

# Add a development dependency
uv add --dev package_name
```

## 🚀 Deployment

Deploy the Datasette interface to Fly.io:

```bash
datasette publish fly data/portland.db --app="data-knowportland"
```

This deploys to: https://data.knowportland.org.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

1. Clone the repository
2. Follow the [Installation](#installation) steps
3. Run tests and linting before submitting changes

## 📄 License

This project is licensed under the Apache 2 license - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Portland eFiles system for providing public meeting data
- Simon Willison for his tools Datatasette, sqlite-utils and llm
