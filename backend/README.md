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

The backend implements the frozen OTP, profile, catalogue draft, media, voice,
and explainable-pricing workflow contract with transactional PostgreSQL
persistence. Request an OTP with an `Idempotency-Key` header, then verify it
with the development code `123456`. Users, profiles, consent, retry records,
drafts, media metadata, transcripts, and pricing suggestions survive server
restarts. OTPs are stored as keyed hashes and are consumed atomically.

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
- `POST /api/v1/catalog/drafts/{draft_id}/images`
- `POST /api/v1/catalog/drafts/{draft_id}/images/{image_id}/enhance`
- `PATCH /api/v1/catalog/drafts/{draft_id}/images/{image_id}`
- `POST /api/v1/catalog/drafts/{draft_id}/voice-notes`
- `POST /api/v1/catalog/drafts/{draft_id}/generate-listing`
- `POST /api/v1/catalog/drafts/{draft_id}/pricing/suggest`
- `GET /api/v1/operations/{operation_id}`

Draft creation requires a UUID `Idempotency-Key`. Draft updates require the
latest `version`; stale writes return `409 VERSION_CONFLICT` so the frontend can
refetch before retrying. The catalogue service owns persistence behind the HTTP
routes, so later media, AI, and approval work does not change the Flutter-facing
draft contract.

## Development media workflow

Image uploads accept decoded JPEG, PNG, or WebP files up to the configured byte
and pixel limits. Original files are preserved, upload and enhancement starts
are idempotent, and the first image is always the draft's primary image. The
mock enhancement provider produces a deterministic square JPEG so frontend
integration can exercise the complete asynchronous operation-polling flow.

`MEDIA_STORAGE=local` writes files atomically beneath `MEDIA_LOCAL_DIR` and
serves them from `MEDIA_URL_BASE`. This is a development adapter: its URLs are
unguessable but not authenticated. Do not use it for private production draft
media; production must use a private object store with short-lived signed URLs.
The original is never replaced, and an enhanced image is used only after the
artisan explicitly selects that variant.

## Local speech transcription

Voice uploads accept decoded M4A, MP3, WAV, or WebM audio up to 25 MB and 120
seconds. The original bytes, duration, hash, language, and idempotent response
snapshot are persisted. Listing generation transcribes the selected voice note
with local `faster-whisper`; no speech API key or BHASHINI credential is used.

The model is loaded lazily on the first generation request. The default
`WHISPER_MODEL_SIZE=small`, CPU `int8` configuration favors Hindi accuracy while
remaining practical on a development laptop. The first request downloads the
model into `WHISPER_MODEL_CACHE_DIR`; pre-warm that cache while online before a
demo. Model files are ignored by Git.

The current catalogue-generation provider is intentionally conservative: it
stores the real transcript and creates only a grounded listing scaffold. It
does not translate or infer unspoken product facts; missing fields remain
explicit for artisan confirmation. A later LLM provider can fill those fields
behind the same frozen HTTP contract.

## Explainable pricing

Pricing suggestions are deterministic backend calculations, not AI-generated
prices. The calculation combines the artisan's material, labour, packaging,
and logistics inputs with a versioned benchmark category. Every response
includes the full cost breakdown, benchmark source label and date, confidence,
and an `is_demo_data` flag. Suggestions are advice only and never force the
final approved selling price.

The repository currently ships clearly labelled demo benchmark rows for local
and integration testing. Replace them with reviewed, attributable benchmark
data before production use. Pricing requests require both the current draft
`version` and a UUID `Idempotency-Key`; retries return the original response
without incrementing the draft twice.

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
The migration enables Row Level Security on every application table. Sensitive
records have no direct client policies and remain restricted to this backend;
the non-sensitive demo pricing benchmark table has a read-only policy.

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
