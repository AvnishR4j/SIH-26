# Hackathon Deployment

Deploy the FastAPI backend as a Render Blueprint from this repository's
`render.yaml`. The Android app is distributed as an APK and connects to the
Render HTTPS URL; it is not deployed as a website.

## Required accounts

- Render: hosts the FastAPI API.
- Supabase: hosts PostgreSQL and catalogue media.

## Supabase setup

1. Create a project in the region closest to the demo audience.
2. Create two Storage buckets:
   - `kalasetu-private` with public access disabled.
   - `kalasetu-public` with public access enabled.
3. Copy the Session pooler connection string from **Connect** for
   `DATABASE_URL` and add `?sslmode=require` if it is not already present.
4. Copy the project URL and server-side secret key. Never put either value in
   Flutter, Git, screenshots, or an APK.

## Render setup

1. In Render, select **New > Blueprint** and connect `AvnishR4j/SIH-26`.
2. Render reads `render.yaml` and prompts for the variables marked as secrets.
3. Set `DEV_OTP=123456` only for the hackathon demo.
4. Set `DEMO_OTP_ALLOWED_PHONE_E164S` as a JSON list of invited test numbers,
   for example `["+919999999999"]`.
5. Set `ADMIN_PHONE_E164` to the administrator's E.164 number.
6. Set the Supabase database URL, project URL, server-side secret key, and the
   Gemini API key.
7. Deploy, then confirm `https://<service>.onrender.com/api/v1/health` reports
   `status: ok` before building the APK.

The configured faster-whisper medium model and image enhancement model are
large. The Blueprint selects Render's `1c-2g` plan and a 5 GB persistent disk
for the model cache. Do not switch it to the free plan: free services sleep and
cannot keep a persistent disk, so they must download the models again after
restarts.

## Android release APK

After the Render URL is healthy, build with:

```bash
cd frontend
flutter build apk --release \
  --dart-define=API_BASE_URL=https://<service>.onrender.com/api/v1 \
  --dart-define=USE_MOCK_API=false
```

Share `frontend/build/app/outputs/flutter-apk/app-release.apk` with invited
testers. They can install it without USB and sign in only with a phone number
in the demo allowlist using the demo OTP.
