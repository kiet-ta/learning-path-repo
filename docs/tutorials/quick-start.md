# Quick Start — 5 Minutes to Your First Learning Path

This tutorial gets you from a fresh clone to a rendered roadmap as fast as possible.
It skips explanation — see [Getting Started](../user_guide/getting_started.md) for the full guide.

---

## Minute 1 — Install

```bash
git clone https://github.com/kiet-ta/learning-path-repo.git
cd learning-path-repo

cp .env.example .env
# Set REPO_SCAN_PATH and OPENAI_API_KEY in .env

pip install -r requirements.txt
```

---

## Minute 2 — Start the backend

```bash
uvicorn api.main:app --reload
```

Verify it's alive:
```bash
curl http://localhost:8000/api/v1/health
# → {"status": "healthy", ...}
```

---

## Minute 3 — Scan your repositories

Point the scanner at a folder that contains your git repos:

```bash
curl -X POST http://localhost:8000/api/v1/scan/batch \
  -H "Content-Type: application/json" \
  -d '{"path": "/home/you/code"}'
```

Or scan a single repo:
```bash
curl -X POST http://localhost:8000/api/v1/scan/repository \
  -H "Content-Type: application/json" \
  -d '{"path": "/home/you/code/my-project"}'
```

You'll get back a list of discovered repositories with their detected languages and skill levels.

---

## Minute 4 — Generate a learning path

```bash
curl -X POST http://localhost:8000/api/v1/learning-paths \
  -H "Content-Type: application/json" \
  -d '{
    "learner_id": "your-name",
    "name": "My Roadmap",
    "description": "Auto-generated from local repos"
  }'
```

Response includes a `path_id` — keep it for later.

---

## Minute 5 — Open the frontend

```bash
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173/roadmap** — your interactive roadmap is ready.

---

## What's next?

| Goal | Where to look |
|------|--------------|
| Set up a local LLM (no OpenAI key) | [Getting Started → Local Model](../user_guide/getting_started.md#5--using-a-local-model-no-api-key-required) |
| Understand the architecture | [System Overview](../architecture/system-overview.md) |
| Track progress per repository | Open `/progress` in the frontend |
| Export roadmap as PDF | Open `/export` in the frontend |
| Run via Docker | `docker-compose up --build` |
| Run tests | `pytest tests/unit/` |

---

## Common first-run issues

```bash
# Wrong: running from inside a subdirectory
cd api && uvicorn main:app        # ✗ — can't find domain/

# Correct: always run from project root
uvicorn api.main:app --reload     # ✓
```

```bash
# If chromadb or tree-sitter give ImportError:
pip install --upgrade chromadb tree-sitter tree-sitter-python
```
