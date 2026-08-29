# KalaSetu Backend

FastAPI backend for the KalaSetu AI MVP. The HTTP interface must follow
`../docs/API_CONTRACT.md`.

## Local setup

From the repository root:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
backend/.venv/bin/uvicorn app.main:app --app-dir backend --reload
```

Open:

- API health: `http://localhost:8000/api/v1/health`
- Swagger: `http://localhost:8000/docs`

Run tests:

```bash
backend/.venv/bin/python -m pytest backend/tests
```
