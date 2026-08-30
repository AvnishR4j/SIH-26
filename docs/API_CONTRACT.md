# KalaSetu AI API Contract

This document is the integration source of truth for the KalaSetu AI MVP. Avnish implements these HTTP interfaces; Amarjit builds against the same schemas using mocks until each route is marked ready.

## Contract Metadata

| Item | Value |
| --- | --- |
| Contract version | `0.2.0-frozen` |
| API version | `v1` |
| Last reviewed | `2026-08-29` |
| Backend owner | Avnish |
| Frontend reviewer | Amarjit |
| Target clients | Flutter Android app and public web share page |
| OpenAPI URL in development | `http://localhost:8000/docs` |

Avnish and Amarjit reviewed and froze this contract as `0.2.0-frozen`. A merged pull request is required for every later contract change.

## MVP Boundary And Route Status

The first complete user journey is:

```text
request OTP -> verify OTP -> create draft -> upload image -> upload voice
-> generate listing -> confirm fields -> suggest price -> approve -> share
```

| Priority | Capability | Endpoint group | Status |
| --- | --- | --- | --- |
| 1 | Service check | `GET /api/v1/health` | `mocked` |
| 2 | OTP login | `/auth/*` | `mocked` |
| 3 | Artisan profile | `/me` | `mocked` |
| 4 | Catalogue drafts | `/catalog/drafts*` | `mocked` |
| 5 | Image upload and enhancement | draft image routes | `mocked` |
| 6 | Voice upload and listing generation | draft voice and generation routes | `mocked` |
| 7 | Explainable pricing | draft pricing route | `planned` |
| 8 | Approval and buyer sharing | approve, share, and enquiry routes | `planned` |

Allowed status values:

- `planned`: specified here but not implemented.
- `mocked`: route works with deterministic demo data.
- `ready`: route is implemented, tested, and available for frontend integration.
- `blocked`: route cannot currently be integrated; the reason must be recorded in its PR.

Do not use `changed` as a route status. Contract changes are recorded in the change log and communicated explicitly.

## Transport Rules

### URLs and content types

- Development server: `http://localhost:8000`
- API prefix: `/api/v1`
- Endpoint headings below are implementation paths relative to `/api/v1`. The effective client URL is always `development server + API prefix + endpoint path`; therefore `GET /health` is called as `GET http://localhost:8000/api/v1/health` in local development.
- Public share pages use the separately configured frontend origin. In local development, `PUBLIC_SHARE_WEB_BASE_URL=http://localhost:3000`; it is not the API server origin.
- JSON requests use `Content-Type: application/json`.
- Uploads use `multipart/form-data`; the client must let its HTTP library generate the multipart boundary.
- Successful JSON responses use `application/json; charset=utf-8`.
- Protected routes use `Authorization: Bearer <access_token>`.
- `/health`, `/share/{public_share_id}`, and the enquiry endpoint are public.

### Data conventions

- JSON field names use `snake_case`.
- IDs are opaque strings. The frontend must never parse or generate IDs returned by the API.
- Timestamps are ISO 8601 UTC strings, for example `2026-08-29T10:30:00Z`.
- Calendar dates use `YYYY-MM-DD`.
- Phone numbers use E.164 format, for example `+919999999999`.
- Language codes use lowercase ISO 639-1 values for the MVP: `hi` and `en`.
- Money is an integer number of INR paise. The frontend formats `95000` as `₹950.00`.
- Confidence scores are numbers from `0.0` to `1.0`. Confidence labels are `low`, `medium`, or `high`.
- A missing JSON field means "leave unchanged" in a PATCH request. Explicit `null` clears a nullable field.
- Unknown response fields must be ignored so additive backend changes do not break older clients.
- Media URL fields are absolute. Private draft-media URLs may be short-lived, so the frontend must not construct or permanently cache them; only the artisan-selected share image becomes public.
- The backend must never expose local filesystem paths, secrets, private object-storage keys, or provider responses.

### Retry and duplicate protection

The mobile app may retry requests after weak connectivity. It sends a UUID in the `Idempotency-Key` header for these operations:

- Request OTP
- Create draft
- Upload image or voice note
- Start enhancement or listing generation
- Suggest a price
- Approve draft
- Submit buyer enquiry

The idempotency scope is the authenticated user ID when auth exists. For public routes, it is the route's stable subject: normalized phone number for OTP and public share ID for an enquiry. Within that scope, repeating the same key and request body returns the original response. Reusing a key with a different body returns `409 IDEMPOTENCY_CONFLICT`.

The replay window is 60 seconds for OTP requests and 24 hours for every other operation above. The frontend must persist the key with a queued request and reuse it for network retries; generating a new key for each retry defeats duplicate protection.

For OTP, the backend performs the idempotency lookup before rate-limit evaluation or OTP generation. Replaying the same key with the same request body returns the stored response, sends no new OTP, and consumes no additional rate-limit quota. A request with a new key is a new OTP attempt and counts toward the limit.

### Pagination

List endpoints accept:

- `limit`: integer from `1` to `50`, default `20`.
- `cursor`: opaque cursor returned by the previous response.

List response shape:

```json
{
  "items": [],
  "next_cursor": null
}
```

`next_cursor` is `null` when there is no next page.

### Draft version protection

Every draft has an integer `version`. PATCH and approval requests include the latest version seen by the frontend. A stale write returns `409 VERSION_CONFLICT` and includes `current_version` in `error.details`; the frontend then refetches the draft before asking the user to retry.

## HTTP Status And Error Rules

| Status | Use |
| --- | --- |
| `200 OK` | Successful read, update, login, or synchronous calculation |
| `201 Created` | Draft, media, approved catalogue, or enquiry created |
| `202 Accepted` | OTP or asynchronous AI operation accepted |
| `204 No Content` | Successful deletion if a delete route is added later |
| `400 Bad Request` | Malformed request or invalid state transition |
| `401 Unauthorized` | Missing, invalid, or expired access token |
| `403 Forbidden` | Authenticated user does not own or cannot access the resource |
| `404 Not Found` | Resource does not exist; do not reveal another user's private resource |
| `409 Conflict` | Version, idempotency, or resource-state conflict |
| `413 Content Too Large` | Upload exceeds the documented size limit |
| `415 Unsupported Media Type` | Unsupported image or audio type |
| `422 Unprocessable Content` | Field validation failed |
| `429 Too Many Requests` | OTP, enquiry, or API rate limit exceeded |
| `500 Internal Server Error` | Unexpected backend failure |
| `503 Service Unavailable` | Required AI or storage provider is temporarily unavailable |

Every non-2xx response uses exactly this shape:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Some fields need attention.",
    "details": {
      "fields": {
        "phone": "Use an E.164 phone number such as +919999999999."
      }
    },
    "request_id": "req_01J6F7ABCD"
  }
}
```

`message` is safe to display to a user. `details` is always an object and may be empty. The frontend branches on `code`, not on message text.

Stable MVP error codes:

- `VALIDATION_ERROR`
- `INVALID_STATE`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_FOUND`
- `VERSION_CONFLICT`
- `IDEMPOTENCY_CONFLICT`
- `RATE_LIMITED`
- `UPLOAD_TOO_LARGE`
- `UNSUPPORTED_MEDIA_TYPE`
- `CONSENT_REQUIRED`
- `AI_SERVICE_UNAVAILABLE`
- `STORAGE_UNAVAILABLE`
- `INTERNAL_ERROR`

The FastAPI backend must override its default validation error body so it matches this contract.

## Shared Enums And Lifecycles

### Draft status

```text
draft -> media_ready -> processing -> needs_confirmation -> ready_for_approval -> approved
                              |               |
                              +---- failed ---+
```

| Value | Meaning |
| --- | --- |
| `draft` | Draft exists; media may still be missing |
| `media_ready` | Required image and voice note exist |
| `processing` | An AI operation is running |
| `needs_confirmation` | Generated or uncertain fields need artisan review |
| `ready_for_approval` | Required fields, selected image, bilingual listing, and price suggestion are complete |
| `approved` | Immutable approved catalogue was created |
| `failed` | Last processing operation failed; draft remains editable and retryable |

The frontend must use the status value for behavior and may map it to translated display text. It must not infer status from missing fields alone.

### Operation status

Asynchronous image enhancement and listing generation use `queued`, `running`, `succeeded`, or `failed`. The client polls the operation URL only while the status is `queued` or `running`.

Image `enhancement_status` uses `not_started`, `queued`, `running`, `succeeded`, or `failed`. Voice-note `status` is `uploaded`; transcription progress belongs to the listing-generation operation, not the voice-note resource.

## Canonical Resource Shapes

Endpoint examples may omit unchanged nested values for readability. When an endpoint says it returns a `Draft`, it returns the complete shape below.

### Draft

```json
{
  "id": "draft_001",
  "version": 4,
  "status": "needs_confirmation",
  "craft_category": "textile",
  "source_language": "hi",
  "initial_notes": "Hand embroidered cotton dupatta",
  "fields": {
    "product_type": "dupatta",
    "material": "cotton",
    "technique": "chikankari embroidery",
    "color": "white",
    "dimensions": null,
    "quantity_available": 3,
    "production_time_days": 5,
    "care": "Gentle hand wash",
    "origin": "Lucknow, Uttar Pradesh"
  },
  "listing": {
    "title_hi": "हाथ की कढ़ाई वाला कॉटन दुपट्टा",
    "title_en": "Hand Embroidered Cotton Dupatta",
    "description_hi": "सफेद कॉटन पर हाथ से की गई कढ़ाई वाला दुपट्टा।",
    "description_en": "A white cotton dupatta with detailed hand embroidery.",
    "tags": ["cotton dupatta", "hand embroidery", "chikankari"]
  },
  "images": [
    {
      "id": "img_001",
      "original_url": "http://localhost:8000/media/img_001_original.jpg",
      "enhanced_url": "http://localhost:8000/media/img_001_enhanced.jpg",
      "is_primary": true,
      "selected_variant": null,
      "enhancement_status": "succeeded",
      "created_at": "2026-08-29T10:32:00Z"
    }
  ],
  "voice_notes": [
    {
      "id": "voice_001",
      "language": "hi",
      "status": "uploaded",
      "duration_seconds": 24,
      "created_at": "2026-08-29T10:33:00Z"
    }
  ],
  "transcript": {
    "voice_note_id": "voice_001",
    "language": "hi",
    "text": "यह सफेद कॉटन का दुपट्टा है और इस पर हाथ की चिकनकारी है।"
  },
  "field_confidence": {
    "product_type": 0.94,
    "material": 0.88,
    "technique": 0.81
  },
  "missing_fields": ["dimensions"],
  "pricing": null,
  "last_processing_error": null,
  "created_at": "2026-08-29T10:30:00Z",
  "updated_at": "2026-08-29T10:35:00Z"
}
```

Before generation, `listing`, `transcript`, and `pricing` may be `null`; `images`, `voice_notes`, `field_confidence`, and `missing_fields` remain arrays or objects, never `null`. Unknown facts must be `null`, not invented by AI.

### Pricing suggestion

```json
{
  "draft_id": "draft_001",
  "draft_version": 7,
  "suggested_min_paise": 85000,
  "suggested_max_paise": 120000,
  "recommended_paise": 95000,
  "confidence": "medium",
  "breakdown": {
    "material_cost_paise": 30000,
    "labour_cost_paise": 40000,
    "packaging_cost_paise": 5000,
    "logistics_buffer_paise": 0,
    "minimum_sustainable_price_paise": 75000,
    "market_reference_low_paise": 80000,
    "market_reference_high_paise": 140000
  },
  "reasons": [
    "The minimum includes material, labour, and packaging costs.",
    "The benchmark category has limited comparable products."
  ],
  "benchmark_category": "cotton_dupatta",
  "benchmark_source_label": "Demo benchmark dataset",
  "benchmark_source_date": "2026-08-29",
  "is_demo_data": true
}
```

### Operation

```json
{
  "id": "op_001",
  "type": "generate_listing",
  "status": "queued",
  "resource_type": "draft",
  "resource_id": "draft_001",
  "poll_after_seconds": 2,
  "error": null,
  "created_at": "2026-08-29T10:34:00Z",
  "updated_at": "2026-08-29T10:34:00Z"
}
```

When an operation succeeds, the frontend refetches the associated draft. When it fails, `error` uses the inner error fields `code`, `message`, and `details`.

## Endpoints

### 1. Health

#### `GET /health`

Effective client route: `GET /api/v1/health`. Auth: public. Success: `200 OK`.

```json
{
  "status": "ok",
  "service": "kalasetu-api",
  "version": "0.1.0",
  "environment": "development"
}
```

`status` may be `ok` or `degraded`. A degraded response still uses HTTP 200 when the API can serve basic requests.

### 2. Authentication

For the prototype, OTP delivery may be mocked or console-logged in development. Production-like responses must not reveal whether a phone number already exists.

#### `POST /auth/request-otp`

Auth: public. Headers: `Idempotency-Key`. Success: `202 Accepted`. OTP idempotency lasts 60 seconds. An idempotent replay does not consume rate-limit quota; a request with a new key does.

Request:

```json
{
  "phone": "+919999999999"
}
```

Response:

```json
{
  "request_id": "otp_req_123",
  "expires_in_seconds": 300,
  "retry_after_seconds": 30
}
```

Rate limit: maximum 5 requests per phone number per 15 minutes in non-test environments.

#### `POST /auth/verify-otp`

Auth: public. Success: `200 OK`.

Request:

```json
{
  "request_id": "otp_req_123",
  "otp": "123456"
}
```

Response:

```json
{
  "access_token": "dev.jwt.token",
  "token_type": "bearer",
  "expires_in_seconds": 86400,
  "user": {
    "id": "usr_001",
    "name": "Sita Devi",
    "phone": "+919999999999",
    "role": "artisan",
    "preferred_language": "hi"
  }
}
```

MVP behavior: no refresh-token route. After expiry, the app requests a new OTP.

### 3. Artisan Profile

#### `GET /me`

Auth: bearer. Success: `200 OK`.

```json
{
  "id": "usr_001",
  "name": "Sita Devi",
  "phone": "+919999999999",
  "role": "artisan",
  "preferred_language": "hi",
  "cluster": "Lucknow Chikankari SHG",
  "craft_categories": ["textile", "embroidery"],
  "consent": {
    "media_processing_accepted": true,
    "media_processing_accepted_at": "2026-08-29T10:20:00Z",
    "policy_version": "2026-08-29"
  }
}
```

`role` is one of `artisan`, `facilitator`, or `admin`. An artisan cannot assign their own role.

#### `PATCH /me`

Auth: bearer. Success: `200 OK`. Response: complete profile shape from `GET /me`.

Allowed request fields:

```json
{
  "name": "Sita Devi",
  "preferred_language": "hi",
  "cluster": "Lucknow Chikankari SHG",
  "craft_categories": ["textile", "embroidery"]
}
```

#### `PUT /me/consents/media-processing`

Auth: bearer. Success: `200 OK`.

```json
{
  "accepted": true,
  "policy_version": "2026-08-29"
}
```

Response:

```json
{
  "media_processing_accepted": true,
  "media_processing_accepted_at": "2026-08-29T10:20:00Z",
  "policy_version": "2026-08-29"
}
```

The app presents the plain-language policy before sending acceptance. `policy_version` must match the current version published by the backend. Sending `accepted: false` records withdrawal for future processing; it does not silently delete existing data. Image enhancement and voice/listing AI return `403 CONSENT_REQUIRED` unless current consent is recorded.

### 4. Catalogue Drafts

#### `POST /catalog/drafts`

Auth: bearer. Headers: `Idempotency-Key`. Success: `201 Created`. Response: complete `Draft`.

```json
{
  "craft_category": "textile",
  "source_language": "hi",
  "initial_notes": "Hand embroidered cotton dupatta"
}
```

`craft_category` and `source_language` are required. `initial_notes` is optional and limited to 1000 characters.

#### `GET /catalog/drafts`

Auth: bearer. Success: `200 OK`.

Query parameters: standard `limit` and `cursor`, plus optional `status`. Drafts are ordered by `updated_at` descending.

```json
{
  "items": [
    {
      "id": "draft_001",
      "version": 4,
      "status": "needs_confirmation",
      "title_hi": "हाथ की कढ़ाई वाला कॉटन दुपट्टा",
      "title_en": "Hand Embroidered Cotton Dupatta",
      "thumbnail_url": "http://localhost:8000/media/img_001_thumb.jpg",
      "recommended_price_paise": 95000,
      "updated_at": "2026-08-29T10:35:00Z"
    }
  ],
  "next_cursor": null
}
```

Summary fields that are not available yet are `null`.

#### `GET /catalog/drafts/{draft_id}`

Auth: bearer. Success: `200 OK`. Response: complete `Draft`.

#### `PATCH /catalog/drafts/{draft_id}`

Auth: bearer. Success: `200 OK`. Response: complete updated `Draft`.

```json
{
  "version": 4,
  "fields": {
    "quantity_available": 2,
    "dimensions": "2.4 m x 1 m"
  },
  "listing": {
    "title_en": "Hand Embroidered Chikankari Cotton Dupatta"
  }
}
```

`version` is required. Only supplied nested fields change. User-confirmed values replace AI confidence for those fields and remove them from `missing_fields` when valid.

#### `POST /catalog/drafts/{draft_id}/approve`

Auth: bearer. Headers: `Idempotency-Key`. Success: `201 Created`.

```json
{
  "version": 7,
  "approved_price_paise": 95000,
  "price_override_reason": null,
  "approval_note": "Artisan confirmed the title, image, product facts, and price."
}
```

`price_override_reason` is required when the approved price is outside the latest suggested range. Approval fails with `400 INVALID_STATE` until the readiness rules below are satisfied.

MVP approval readiness requires:

- `craft_category`, `product_type`, `material`, `technique`, `dimensions`, `quantity_available`, and `production_time_days`.
- One primary image with `selected_variant` set to `original` or `enhanced`.
- Non-empty Hindi and English titles and descriptions.
- A current pricing suggestion and a positive `approved_price_paise`.
- No generation or enhancement operation still queued or running for the selected content.

The pricing suggestion is current only when its `draft_version` equals the draft's latest `version`; editing the draft afterward requires a new suggestion. `quantity_available` must be an integer of at least `1`, `production_time_days` must be a non-negative integer, and required text fields must not be blank.

`color`, `care`, `origin`, tags, and `approval_note` are optional. The backend returns missing readiness items in `error.details.fields` so the frontend can take the artisan to the correct step.

Response:

```json
{
  "id": "cat_001",
  "draft_id": "draft_001",
  "status": "approved",
  "approved_price_paise": 95000,
  "currency": "INR",
  "public_share_id": "share_abc123",
  "public_share_url": "http://localhost:3000/share/share_abc123",
  "created_at": "2026-08-29T10:50:00Z"
}
```

The backend constructs `public_share_url` as `PUBLIC_SHARE_WEB_BASE_URL + /share/{public_share_id}`. The example uses the local frontend origin from `.env.example`; production uses the configured HTTPS web origin.

An approved draft and its catalogue snapshot are immutable in the MVP. `PATCH /catalog/drafts/{draft_id}` and image PATCH requests against an approved draft return `400 INVALID_STATE`. There is no edit-approved or clone-catalogue endpoint in `v1`; to revise a product, the client creates a new independent draft through `POST /catalog/drafts` and the user supplies or confirms its values again.

### 5. Images And Enhancement

#### `POST /catalog/drafts/{draft_id}/images`

Auth: bearer. Headers: `Idempotency-Key`. Content: multipart. Success: `201 Created`.

Multipart fields:

- `image`: required JPEG, PNG, or WebP file, maximum 10 MB.
- `is_primary`: optional boolean string, default `true`.

A draft with images has exactly one primary image. The first uploaded image becomes primary even if `is_primary` is `false`. For later uploads, `is_primary: true` atomically unsets the previous primary and selects the new image; `is_primary: false` preserves the existing primary. Multiple primary images are never allowed.

Response:

```json
{
  "id": "img_001",
  "original_url": "http://localhost:8000/media/img_001_original.jpg",
  "enhanced_url": null,
  "is_primary": true,
  "selected_variant": null,
  "enhancement_status": "not_started",
  "created_at": "2026-08-29T10:32:00Z"
}
```

The backend validates the decoded file, not only the filename or browser-provided MIME type. The original is preserved.

#### `POST /catalog/drafts/{draft_id}/images/{image_id}/enhance`

Auth: bearer. Headers: `Idempotency-Key`. Success: `202 Accepted`. Response: `Operation` with type `enhance_image`. The response also includes `Location: /api/v1/operations/{operation_id}`.

```json
{
  "background": "neutral",
  "crop_style": "marketplace_square",
  "preserve_original": true
}
```

`background`: `neutral` or `keep_original`. `crop_style`: `marketplace_square` or `keep_original`. `preserve_original` must be `true` in the MVP.

#### `PATCH /catalog/drafts/{draft_id}/images/{image_id}`

Auth: bearer. Success: `200 OK`. Response: complete updated `Draft`.

```json
{
  "version": 5,
  "is_primary": true,
  "selected_variant": "enhanced"
}
```

`version` is required and participates in draft version protection; a stale value returns `409 VERSION_CONFLICT`. `selected_variant` is `original` or `enhanced`. The enhanced variant can be selected only after enhancement succeeds. This explicit action is the artisan's image approval; AI processing never selects a public image on the artisan's behalf.

Setting `is_primary: true` atomically unsets the previous primary. Setting it to `false` on the current primary is rejected with `400 INVALID_STATE`; because the MVP PATCH changes one image at a time, clients should promote the replacement image instead.

### 6. Voice And Listing Generation

#### `POST /catalog/drafts/{draft_id}/voice-notes`

Auth: bearer. Headers: `Idempotency-Key`. Content: multipart. Success: `201 Created`.

Multipart fields:

- `audio`: required M4A, MP3, WAV, or WebM file, maximum 25 MB and 120 seconds.
- `language`: required; `hi` for the first pilot.

Response:

```json
{
  "id": "voice_001",
  "language": "hi",
  "status": "uploaded",
  "duration_seconds": 24,
  "created_at": "2026-08-29T10:33:00Z"
}
```

#### `POST /catalog/drafts/{draft_id}/generate-listing`

Auth: bearer. Headers: `Idempotency-Key`. Success: `202 Accepted`. Response: `Operation` with type `generate_listing`. The response also includes `Location: /api/v1/operations/{operation_id}`.

```json
{
  "voice_note_id": "voice_001",
  "image_id": "img_001",
  "target_languages": ["hi", "en"]
}
```

Generation updates the existing draft; it never approves or publicly shares it. The AI may only draft facts grounded in user input or confirmed fields. Uncertain facts remain in `missing_fields`.

#### `GET /operations/{operation_id}`

Auth: bearer. Success: `200 OK`. Response: complete `Operation`.

Recommended polling behavior: wait for `poll_after_seconds`, stop after 60 seconds in the foreground, and allow the user to leave the screen. Refetch the operation later instead of starting a duplicate job.

### 7. Pricing Assistant

#### `POST /catalog/drafts/{draft_id}/pricing/suggest`

Auth: bearer. Headers: `Idempotency-Key`. Success: `200 OK`. Response: complete `Pricing suggestion`; `draft_version` is the draft version after the suggestion is stored.

```json
{
  "version": 6,
  "material_cost_paise": 30000,
  "labour_hours": 8.0,
  "hourly_rate_paise": 5000,
  "packaging_cost_paise": 5000,
  "logistics_buffer_paise": 0,
  "benchmark_category": "cotton_dupatta"
}
```

All money values are non-negative integers. `labour_hours` is greater than `0` and at most `10000`. The result always identifies its source date and whether demo data was used. It is advice, never an enforced selling price.

### 8. Buyer Share And Enquiries

#### `GET /share/{public_share_id}`

Auth: public. Success: `200 OK`.

```json
{
  "catalog_id": "cat_001",
  "title": "Hand Embroidered Chikankari Cotton Dupatta",
  "description": "A white cotton dupatta with detailed hand embroidery.",
  "image_url": "http://localhost:8000/media/img_001_enhanced.jpg",
  "price_paise": 95000,
  "currency": "INR",
  "quantity_available": 2,
  "artisan": {
    "display_name": "Sita Devi",
    "cluster": "Lucknow Chikankari SHG"
  },
  "enquiry_enabled": true,
  "published_at": "2026-08-29T10:50:00Z"
}
```

This response must not expose the artisan's phone number, private media, internal IDs other than `catalog_id`, cost breakdown, or AI confidence values.

#### `POST /share/{public_share_id}/enquiries`

Auth: public. Headers: `Idempotency-Key`. Success: `201 Created`.

```json
{
  "buyer_name": "Aarav Retail",
  "buyer_phone": "+918888888888",
  "message": "Interested in 20 pieces",
  "quantity_requested": 20,
  "consent_to_contact": true
}
```

`buyer_name`, `buyer_phone`, and `consent_to_contact: true` are required. Apply rate limiting and do not reveal whether internal notifications succeeded.

Response:

```json
{
  "enquiry_id": "enq_001",
  "status": "received",
  "received_at": "2026-08-29T11:00:00Z"
}
```

## Frontend Integration Interface

Amarjit should expose these functions from one API client layer. Screens should not call HTTP directly.

```text
requestOtp(phone, idempotencyKey)
verifyOtp(requestId, otp)
getMe()
updateMe(patch)
setMediaProcessingConsent(input)
listDrafts(query)
getDraft(draftId)
createDraft(input, idempotencyKey)
updateDraft(draftId, patch)
uploadDraftImage(draftId, file, idempotencyKey)
enhanceDraftImage(draftId, imageId, options, idempotencyKey)
selectDraftImageVariant(draftId, imageId, input)
uploadVoiceNote(draftId, file, language, idempotencyKey)
generateListing(draftId, input, idempotencyKey)
getOperation(operationId)
suggestPrice(draftId, input, idempotencyKey)
approveDraft(draftId, input, idempotencyKey)
getShareCard(publicShareId)
submitEnquiry(publicShareId, input, idempotencyKey)
```

Mock responses must be copied from fixtures that conform to this contract, not embedded separately in screens. Switching from mock to real mode should change only the API client implementation or configuration.

## Contract Acceptance Checklist

An endpoint may move to `ready` only when:

- Its method, path, auth, request, response, and status codes match this document.
- Its OpenAPI schema matches nullable and required fields documented here.
- Success, validation, unauthorised, and not-found behavior have automated tests where applicable.
- Errors use the standard error body.
- The frontend can call it using the shared development base URL.
- Avnish gives Amarjit one working request example and Amarjit confirms the response can replace the mock.

Before merging an integration PR, test at least:

- Normal success
- Slow loading or polling
- Empty list or missing optional fields
- Invalid input
- Expired token for protected routes
- Retry with the same idempotency key
- Weak-network retry without duplicate data

## Contract Change Protocol

Once frozen:

1. The person proposing a change edits this file before implementation.
2. The PR labels the change as `additive`, `behavioral`, or `breaking`.
3. The other teammate reviews the frontend and backend impact.
4. Additive optional fields may ship immediately because clients ignore unknown fields.
5. Renames, removals, type changes, new required fields, path changes, and meaning changes are breaking.
6. A breaking change requires either updating both sides in the same integration window or temporarily supporting both shapes.
7. The change log records the merged decision.

## Deferred Beyond The Core MVP

These are part of the product direction but are deliberately not frozen in `v1` yet:

- PDF/CSV catalogue export
- Indiahandmade or GeM readiness checklist
- Facilitator review queues
- Offline bulk sync endpoint
- Refresh tokens
- Multiple image roles and image deletion
- Marketplace publishing, payments, logistics, and orders

Do not build frontend assumptions for deferred routes until they are added to this contract.

## Change Log

| Date | Version | Type | Summary |
| --- | --- | --- | --- |
| 2026-08-29 | `0.2.0-draft` | behavioral | Normalized draft schemas; added status codes, lifecycle, pagination, idempotency, upload constraints, operation polling, version protection, privacy boundaries, and change governance. |
| 2026-08-29 | `0.2.0-draft` | clarification | Defined public-route idempotency scope and OTP window, approval readiness, media status values, operation location header, and complete pricing breakdown. |
| 2026-08-29 | `0.2.0-frozen` | clarification | Froze the reviewed contract after defining the effective health URL, OTP replay order, single-primary-image invariant, image PATCH version requirement, approved-draft immutability, and configured public share origin. |
| 2026-08-30 | `0.2.0-frozen` | status | Marked implemented health, authentication, profile, and catalogue draft routes as mocked pending Flutter verification. No HTTP interface changed. |
| 2026-08-30 | `0.2.0-frozen` | status | Marked image upload, deterministic mock enhancement, image selection, and operation polling as mocked pending Flutter verification. No HTTP interface changed. |
| 2026-08-30 | `0.2.0-frozen` | status | Marked voice upload, local faster-whisper transcription, grounded listing scaffold, and generation polling as mocked pending Flutter verification. No HTTP interface changed. |
