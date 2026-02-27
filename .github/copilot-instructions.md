# Copilot Instructions — Auto Learning Path Generator

## Architecture Overview

This is a **Clean Architecture / DDD** monorepo with three main components:

1. **Main Backend** (Python/FastAPI) — two parallel structures exist:
   - **Root-level layers** (`domain/`, `application/`, `infrastructure/`, `api/`) — the richer, actively-developed codebase with full DDD entities, value objects, and custom exceptions
   - **`backend/`** — an alternative structure with its own entities, services, tests, and CLI. Contains the test suite (`backend/tests/{unit,integration,e2e}/`)
2. **AI Service** (`ai-service/`) — separate FastAPI microservice for NLP analysis, skill classification, and recommendations, with its own Docker setup
3. **Frontend** (`frontend/`) — React 18 + Vite + Redux + Tailwind CSS + D3.js for interactive roadmap visualization

## Layer Dependency Rules

```
api/ (routers, schemas, middleware) → application/ (use_cases, services, dto) → domain/ (entities, exceptions, value_objects) ← infrastructure/ (persistence, graph, scanner)
```

- **Domain layer has ZERO external dependencies** — only stdlib and own types
- Infrastructure implements domain interfaces; never import infrastructure from domain or application
- API schemas (Pydantic v2 `BaseModel`) live in `api/schemas/` — do NOT mix with domain entities (`dataclass`)
- Use cases orchestrate services; services contain business logic; entities enforce invariants

## Domain Entity Patterns

Entities use `@dataclass` with `__post_init__` for validation. Follow this established pattern:

```python
@dataclass
class MyEntity:
    name: str
    entity_id: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        self._validate()

    def _validate(self):
        if not self.name or not self.name.strip():
            raise ValidationError("name", "Name cannot be empty")
```

- Import exceptions from `domain.exceptions.domain_exceptions` (`ValidationError`, `BusinessRuleViolation`, `CircularDependencyError`)
- Use `UUID` for entity IDs (generated via `uuid4`), not strings or integers
- `LearningPath` is the aggregate root — all mutations to nodes/dependencies go through it

## API Conventions

- All routes prefixed with `/api/v1` (configured in `api/main.py`)
- Routers in `api/routers/` — one file per resource (e.g., `learning_path_router.py`)
- Request/response models in `api/schemas/` using Pydantic v2 with `Field(...)` descriptions
- DI wiring in `api/dependencies/` — use `dependency_injection.py` and `use_case_factory.py`
- Custom middleware: `LoggingMiddleware`, `PerformanceMiddleware`, centralized `error_handler`

## Application Layer Services

Services in `application/services/` handle core orchestration:
- `path_generator_service.py` — main path generation logic
- `topological_sorter.py` — ordering nodes by dependencies
- `graph_builder.py` — builds the dependency graph
- `milestone_grouper.py` — groups nodes into learning milestones
- `override_manager.py` — applies manual user overrides

DTOs in `application/dto/` (`learning_path_request.py`, `learning_path_response.py`, `milestone_group.py`) bridge API and domain layers.

## Infrastructure

- **Persistence**: SQLAlchemy 2.0 models in `infrastructure/persistence/models/`, repository pattern implementations in `infrastructure/persistence/repositories/` (e.g., `sqlite_learning_path_repository.py`)
- **Graph engine**: `infrastructure/graph/` — `dependency_graph.py`, `circular_dependency_resolver.py`, `knowledge_graph.py`, `graph_algorithms.py` (some are stubs awaiting implementation)
- **Scanner**: `infrastructure/scanner/` — `language_detector.py`, `file_system_abstraction.py`

## Frontend

- **Entry**: `frontend/src/App.jsx` — React Router v6 with routes: `/`, `/roadmap`, `/progress`, `/export`
- **State**: Redux store in `frontend/src/store/` (`roadmapSlice.js`, `progressSlice.js`)
- **API calls**: `frontend/src/services/api.js` (Axios-based), `graphService.js`
- **Hooks**: `useRoadmap`, `useProgress`, `useFilters` in `frontend/src/hooks/`
- **Components**: organized by feature in `frontend/src/components/{dashboard,roadmap,export,common}/`
- **Build**: `npm run dev` (Vite), `npm run build` (tsc + Vite)

## Development Commands

```bash
# Backend
pip install -r requirements.txt
uvicorn backend.interfaces.api.main:app --reload        # via backend/ structure
# or
uvicorn api.main:app --reload                            # via root api/ structure

# Frontend
cd frontend && npm install && npm run dev

# Docker (full stack)
docker-compose up --build                                # exposes port 8000

# Tests
cd backend && pytest tests/unit/                         # unit tests
cd backend && pytest tests/integration/                  # integration tests
cd backend && pytest tests/e2e/                          # end-to-end tests
cd ai-service && pytest tests/                           # AI service tests

# Linting & Formatting
black . && isort . && flake8                             # Python
cd frontend && npm run lint && npm run format             # Frontend
```

## Key Dependencies

- **AI/NLP**: OpenAI + LangChain + tiktoken + scikit-learn — configured via `OPENAI_API_KEY` and `MODEL_NAME` env vars
- **Database**: SQLAlchemy 2.0 + Alembic (migrations in `infrastructure/persistence/database/migrations.py`)
- **Git analysis**: GitPython — scans repos at path set by `REPO_SCAN_PATH` env var

## Important Notes

- Many infrastructure files (`graph_algorithms.py`, `knowledge_graph.py`, `nlp_analyzer.py`, `skill_classifier.py`) are **stubs** — implement with the established patterns when working on them
- The `backend/` directory duplicates some domain concepts from root-level `domain/` — prefer root-level `domain/entities/` for richer entity logic; use `backend/` for test infrastructure and CLI
- Env config: copy `.env.example` → `.env` with `OPENAI_API_KEY`, `MODEL_NAME`, `DATABASE_URL`, `REPO_SCAN_PATH`
