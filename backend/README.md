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

## Development authentication

The current prototype implements the frozen OTP, profile, and catalogue draft
contract with in-memory storage. Request an OTP with an `Idempotency-Key`
header, then verify it with the development code `123456`. Restarting the
server clears users, OTP requests, profiles, and catalogue drafts.

Implemented routes:

- `POST /api/v1/auth/request-otp`
- `POST /api/v1/auth/verify-otp`
- `GET /api/v1/me`
- `PATCH /api/v1/me`
- `PUT /api/v1/me/consents/media-processing`
- `POST /api/v1/catalog/drafts`
- `GET /api/v1/catalog/drafts`
- `GET /api/v1/catalog/drafts/{draft_id}`
- `PATCH /api/v1/catalog/drafts/{draft_id}`

Draft creation requires a UUID `Idempotency-Key`. Draft updates require the
latest `version`; stale writes return `409 VERSION_CONFLICT` so the frontend can
refetch before retrying. The catalogue service owns persistence behind the HTTP
routes, allowing Supabase storage to replace the prototype store without an API
contract change.

Run tests:

```bash
backend/.venv/bin/python -m pytest backend/tests
```
