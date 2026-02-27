# Auto Learning Path Generator

🚀 **Automatically generate personalized learning paths from your code repositories**

## Overview

The Auto Learning Path Generator is an intelligent system that analyzes your repositories to create structured learning roadmaps. It uses AI/NLP to understand your codebase, classify skills, and generate optimal learning sequences from basic to advanced topics.

## Features

- 🔍 **Auto Repository Scanning**: Automatically scans all local repositories
- 🧠 **AI-Powered Analysis**: Uses NLP to extract topics, skills, and dependencies
- 🗺️ **Interactive Roadmap**: Visual learning path similar to roadmap.sh
- 📊 **Progress Tracking**: Automatic progress monitoring based on git activity
- 📤 **Export Options**: Generate PDF/HTML reports for team sharing
- 🎯 **Customizable**: Override AI suggestions with manual adjustments

## Architecture

Built with Clean Architecture principles:

- **Domain Layer**: Core business logic and entities
- **Application Layer**: Use cases and services
- **Infrastructure Layer**: AI engine, file system, database
- **Interface Layer**: API and CLI interfaces

## Tech Stack

### Backend
- Python 3.9+
- FastAPI for REST API
- SQLite for data storage
- OpenAI/LangChain for NLP analysis
- GitPython for repository analysis

### Frontend
- React 18+
- D3.js for interactive visualizations
- Redux Toolkit for state management
- Tailwind CSS for styling

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 16+
- Git

### Installation

1. Clone the repository:
```bash
git clone https://github.com/kiet-ta/learning-path-repo.git
cd learning-path-repo
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env — at minimum set REPO_SCAN_PATH and OPENAI_API_KEY (or see Local Model below)
```

3. Backend setup:
```bash
pip install -r requirements.txt
uvicorn api.main:app --reload
# API available at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
```

4. Frontend setup:
```bash
cd frontend
npm install
npm run dev
# UI available at http://localhost:5173
```

## Usage

### Web Interface
1. **Dashboard** (`/`) — Overview of scanned repositories and learning progress
2. **Roadmap** (`/roadmap`) — Interactive D3.js visualization of your learning path; click any node to see repository details
3. **Progress** (`/progress`) — Track your per-repository learning status; mark items as in-progress / completed
4. **Export** (`/export`) — Download your learning path as PDF or HTML report

### REST API
All endpoints are prefixed `/api/v1`. Full interactive documentation at **http://localhost:8000/docs**.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/scan/repository` | Scan a single repository path |
| `POST` | `/api/v1/scan/batch` | Scan multiple repositories at once |
| `POST` | `/api/v1/analyze/{id}` | Run AI analysis on a scanned repository |
| `GET`  | `/api/v1/learning-paths` | List all generated learning paths |
| `POST` | `/api/v1/learning-paths` | Generate a new learning path |
| `GET`  | `/api/v1/repositories` | Browse indexed repositories |
| `GET`  | `/api/v1/progress/{learner_id}` | Get learner progress |

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# --- AI (choose one) ---

# Option A: OpenAI (default)
OPENAI_API_KEY=your_openai_key
MODEL_NAME=gpt-3.5-turbo          # or gpt-4o-mini for lower cost

# Option B: Local model via Ollama (no API key needed)
# 1. Install Ollama: https://ollama.com
# 2. Pull a model: ollama pull mistral
# 3. Set these in .env:
OPENAI_API_KEY=ollama              # dummy value — not sent to OpenAI
MODEL_NAME=mistral                 # any model you've pulled
OPENAI_BASE_URL=http://localhost:11434/v1   # Ollama's OpenAI-compat endpoint

# --- Database ---
DATABASE_URL=sqlite:///data/learning_path.db

# --- Repository Scanning ---
REPO_SCAN_PATH=/path/to/your/repos   # root folder containing git repos
```

### AST Parser — Tree-sitter (Recommended)

The scanner uses **tree-sitter** for accurate code skeleton extraction. Without it the system
falls back to regex (less accurate, especially for nested classes / decorators).

Verify tree-sitter is installed (it's in `requirements.txt`):
```bash
pip install tree-sitter tree-sitter-python tree-sitter-javascript \
            tree-sitter-typescript tree-sitter-java tree-sitter-go tree-sitter-rust
```

If you see `tree-sitter unavailable — regex fallback` in the logs, re-run the above command.

### RAG / Vector Store Persistence

Indexed code embeddings are stored persistently under `data/chroma/` (ChromaDB).
This means after the first `index_repository()` call the vector store survives app restarts —
you will **not** need to re-scan your repositories on every startup.

```bash
# The folder is created automatically; add it to .gitignore (already done)
ls data/chroma/
```

To force a full re-index (e.g. after major code changes):
```bash
# Via API
curl -X POST http://localhost:8000/api/v1/scan/repository \
     -H "Content-Type: application/json" \
     -d '{"path": "/your/repo", "force_reindex": true}'
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Author

**TAK** - Auto Learning Path Generator Project

---

*Built with ❤️ for developers who want to optimize their learning journey*
# learning-path-repo
