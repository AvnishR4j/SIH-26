# Backend Task Plan For Avnish

This is the recommended backend order for the SIH 26090 prototype. It lets Amarjit build the frontend in parallel with stable mocks.

## Phase 0: Agree Contract

- Keep `docs/API_CONTRACT.md` as the source of truth.
- Tell Amarjit when a route is ready, partially ready, or still mocked.
- Do not change response field names casually after frontend work begins.

## Phase 1: Backend Skeleton

- Create FastAPI project structure.
- Add `/api/v1/health`.
- Add environment config.
- Add CORS for the frontend dev URL.
- Add automatic API docs through FastAPI Swagger.
- Add basic test command.

Suggested modules:

```text
app/
  main.py
  core/config.py
  core/security.py
  api/v1/routes/
  models/
  schemas/
  services/
  tests/
```

## Phase 2: Auth And Users

- Implement OTP request and verify endpoints.
- For prototype, allow a development OTP such as `123456`.
- Return a JWT-like access token or real JWT.
- Add artisan profile endpoints.
- Add role field: `artisan`, `facilitator`, `admin`.

Frontend unblocked:

- Login screen
- Profile setup screen
- Authenticated app navigation

## Phase 3: Catalog Draft CRUD

- Create catalog draft.
- List drafts.
- Get draft detail.
- Update draft fields.
- Approve draft into final catalog item.

Frontend unblocked:

- Home dashboard
- Draft list
- Product details editor
- Approval flow

## Phase 4: Media Upload

- Accept product image upload.
- Store original image separately.
- Return stable media URL.
- Add placeholder image-enhancement route.
- Later connect actual image enhancement model/service.

Frontend unblocked:

- Camera/upload screen
- Before/after comparison UI
- Image approval UI

## Phase 5: Voice And Listing Generation

- Accept voice note upload.
- Return stored voice note ID.
- Build `generate-listing` route.
- In early prototype, return deterministic sample extraction from text/audio.
- Later connect ASR, translation and LLM pipeline.

Frontend unblocked:

- Voice recording screen
- Transcript confirmation screen
- Missing-field chips/forms
- Bilingual listing preview

## Phase 6: Pricing Assistant

- Implement cost-plus calculation.
- Add benchmark table for a few craft categories.
- Return price range, confidence, reasons and source date.
- Allow artisan override during approval.

Frontend unblocked:

- Pricing form
- Price recommendation card
- Override reason UI

## Phase 7: Share Card And Enquiries

- Generate public share ID after catalog approval.
- Serve buyer-facing catalog data.
- Accept buyer enquiry.
- Store enquiry status.

Frontend unblocked:

- Public share page
- QR/share button
- Buyer enquiry form

## Phase 8: Demo Polish

- Seed demo users and products.
- Add clear demo media.
- Add useful validation errors.
- Add Swagger screenshots for pitch.
- Ensure one complete flow works end to end:

```text
login -> create draft -> upload image -> upload voice -> generate listing -> suggest price -> approve -> share card
```

## Backend Priorities

Build in this exact priority if time is short:

1. Health, auth, profile
2. Catalog draft CRUD
3. Image upload with mock enhancement
4. Voice upload with mock listing generation
5. Pricing suggestion
6. Share card
7. Real AI integrations

The SIH demo can still be strong if AI routes are mocked cleanly but the workflow, data model and human approval flow are real.
