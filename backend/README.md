# KalaSetu Backend

FastAPI backend for the KalaSetu AI MVP. The HTTP interface must follow
`../docs/API_CONTRACT.md`.

## Local setup

From the repository root:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

Open:

- API health: `http://localhost:8000/api/v1/health`
- Swagger: `http://localhost:8000/docs`

## Development authentication

The current prototype implements the frozen OTP, profile, and catalogue draft
contract with in-memory storage. Request an OTP with an `Idempotency-Key`
header, then verify it with the development code `123456`. Restarting the
server clears users, OTP requests, profiles, and catalogue drafts.

The in-memory store is intentionally limited to local single-process integration.
It now serializes retry and version-sensitive operations, but shared deployment
still requires the planned PostgreSQL/Supabase persistence milestone.

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
