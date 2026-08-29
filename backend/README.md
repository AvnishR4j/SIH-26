# KalaSetu Backend

FastAPI backend for the KalaSetu AI MVP. The HTTP interface must follow
`../docs/API_CONTRACT.md`.

## Local setup

From the repository root:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
cp .env.example .env
backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

Set `DATABASE_URL` in `.env` to a reachable PostgreSQL database before running
the migration. Both `postgresql://` and `postgresql+psycopg://` URLs are
accepted; the backend normalizes them to the installed psycopg 3 driver.

Open:

- API health: `http://localhost:8000/api/v1/health`
- Swagger: `http://localhost:8000/docs`

## Development authentication

The backend implements the frozen OTP, profile, and catalogue draft contract
with transactional PostgreSQL persistence. Request an OTP with an
`Idempotency-Key` header, then verify it with the development code `123456`.
Users, profiles, consent, retry records, and drafts survive server restarts.
OTPs are stored as keyed hashes and are consumed atomically.

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
routes, so later media, AI, and approval work does not change the Flutter-facing
draft contract.

## Database migrations

Run migrations before starting any shared or production-like deployment:

```bash
cd backend
.venv/bin/alembic -c alembic.ini upgrade head
.venv/bin/alembic -c alembic.ini current
.venv/bin/alembic -c alembic.ini check
```

`DATABASE_AUTO_CREATE=true` is available only for isolated development and
tests. Production rejects it so schema changes cannot bypass migration history.

For Supabase, use the server-side direct or Session pooler PostgreSQL URL with
TLS enabled. Never place the database password or a service-role key in Flutter.
The migration enables Row Level Security on every application table without
adding client policies; data access is intentionally restricted to this backend.

Frontend development URLs:

- Android emulator: `http://10.0.2.2:8000/api/v1`
- iOS simulator: `http://127.0.0.1:8000/api/v1`
- Flutter web: `http://localhost:8000/api/v1` using web port `8080`
- Physical phone: `http://<MAC_LAN_IP>:8000/api/v1`

For Flutter web, use a stable port that is included in `CORS_ORIGINS`:

```bash
flutter run -d chrome --web-port 8080 --dart-define=API_BASE_URL=http://localhost:8000/api/v1
```

Run tests:

```bash
backend/.venv/bin/python -m pytest backend/tests
```
