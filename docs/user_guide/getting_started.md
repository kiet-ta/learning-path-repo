# Getting Started

This guide walks you through a full local installation of the Auto Learning Path Generator —
from zero to a running roadmap in your browser.

---

## Prerequisites

| Tool | Minimum version | Notes |
|------|----------------|-------|
| Python | 3.9+ | `python --version` |
| Node.js | 16+ | `node --version` |
| Git | any | needed by GitPython scanner |
| (optional) Ollama | latest | only if using a local LLM instead of OpenAI |

---

## 1 — Clone & Configure

```bash
git clone https://github.com/kiet-ta/learning-path-repo.git
cd learning-path-repo
cp .env.example .env
```

Open `.env` and set **at least** these two values:

```bash
REPO_SCAN_PATH=/home/you/code        # folder that contains your git repos
OPENAI_API_KEY=sk-...                # skip if using Ollama (see section 4)
```

---

## 2 — Backend

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the API server (hot-reload enabled)
uvicorn api.main:app --reload
```

- **REST API** → http://localhost:8000/api/v1
- **Swagger UI** (try any endpoint) → http://localhost:8000/docs
- **Health check** → http://localhost:8000/api/v1/health

> **Tip**: First run creates `data/learning_path.db` (SQLite) and `data/chroma/` (vector store)
> automatically. Both are in `.gitignore` — do not commit them.

---

## 3 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## 4 — Using the Interface

### Dashboard `/`

The home screen shows:
- **Repository count** — total repos discovered under `REPO_SCAN_PATH`
- **Skill distribution** chart — breakdown by skill type (backend, frontend, …)
- **Recent activity** — last 5 repositories you interacted with
- **Quick scan** button — triggers a batch scan of your entire `REPO_SCAN_PATH`

### Roadmap `/roadmap`

An interactive D3.js graph where:
- Each **node** = one repository
- **Edges** = prerequisite relationships (arrow = "learn this first")
- Node **colour** encodes skill level: grey → green → yellow → red (basic → expert)
- **Click** a node to open the detail panel (language, topics, estimated learning time)
- **Drag** nodes to rearrange; the layout is saved in local storage

Keyboard shortcuts:
| Key | Action |
|-----|--------|
| `+` / `-` | Zoom in / out |
| `R` | Reset layout |
| `F` | Fit all nodes to screen |

### Progress `/progress`

Track your learning journey:
1. Click a repository card and choose **Start** to mark it *in-progress*
2. When done, click **Complete** — progress percentage updates automatically
3. Add a **difficulty rating** (1–5) and **notes** for future reference
4. The **streak** counter tracks consecutive days of learning activity

### Export `/export`

Generate a shareable learning roadmap:
- **HTML** — self-contained single file, works offline
- **PDF** — A4 portrait, suitable for printing or sharing with a manager

---

## 5 — Using a Local Model (no API key required)

Instead of OpenAI you can run **Mistral**, **Llama 3**, or any GGUF model locally via [Ollama](https://ollama.com).

### Step 1 — Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh
```

### Step 2 — Pull a model

```bash
ollama pull mistral          # ~4 GB, good balance of speed and quality
# or
ollama pull llama3.2         # latest Meta Llama
# or
ollama pull codellama        # fine-tuned for code analysis
```

### Step 3 — Configure `.env`

```bash
OPENAI_API_KEY=ollama                        # any non-empty string
MODEL_NAME=mistral                           # must match the pulled model name
OPENAI_BASE_URL=http://localhost:11434/v1    # Ollama's OpenAI-compatible API
```

The backend uses the OpenAI Python client, which respects `OPENAI_BASE_URL` — no code changes needed.

> **Performance note**: Code skeleton analysis (via the AST parser) runs locally regardless of which LLM you choose. Only the natural-language summarisation and skill classification calls hit the LLM.

---

## 6 — Tree-sitter (Recommended for accurate analysis)

The scanner extracts code skeletons with **tree-sitter** for precise class/function boundaries.
Without it the system falls back to regex, which misses decorators, nested classes, and type annotations.

```bash
pip install \
  tree-sitter \
  tree-sitter-python \
  tree-sitter-javascript \
  tree-sitter-typescript \
  tree-sitter-java \
  tree-sitter-go \
  tree-sitter-rust
```

All packages are already listed in `requirements.txt`; the command above is only needed if you
installed dependencies manually (e.g. in a bare venv without `-r requirements.txt`).

To verify tree-sitter is active, scan any repository and check the logs:
```
INFO  ASTParser using tree-sitter for python   ✓
```
If you see `regex fallback` instead, re-run the pip install above.

---

## 7 — Docker (optional)

```bash
# Build and start all services
docker-compose up --build

# Backend at :8000, frontend served as static files
```

The Docker image already includes all Python dependencies and the compiled frontend.
Set your `.env` values before running — `docker-compose.yml` reads them via `env_file: .env`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: api` | Run `uvicorn` from the project root, not from a subdirectory |
| Roadmap page is empty | Trigger a scan first: POST `/api/v1/scan/batch` or click **Quick scan** on the dashboard |
| LLM calls time out | Switch to a smaller model (`gpt-3.5-turbo` or `ollama pull tinyllama`) |
| `chromadb` import error | `pip install chromadb>=0.5.23` |
| Vector store rebuilt on every restart | Confirm `data/chroma/` exists and is not in a `tmpfs` mount |
| `409 Conflict` on scan | Repository already indexed; pass `"force_reindex": true` in the request body |
