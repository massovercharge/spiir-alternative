# Development Guide

## Prerequisites
- Node.js (v20+)
- Python (v3.11+)
- Docker (optional, for deployment testing)

## Backend Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,test]"
```
Run API:
```bash
uvicorn app.api:app --app-dir backend --reload --port 8000
```
Run tests:
```bash
pytest backend/tests/
```

## Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

## Formatting
The backend uses `ruff` for linting and formatting. Run `.venv/bin/ruff format backend/` before committing.
