# KalaSetu AI API Contract

This file is the handshake between backend and frontend. Backend should implement these routes; frontend can build screens using the example responses until the real API is ready.

## Base Rules

- Base URL in development: `http://localhost:8000`
- API prefix: `/api/v1`
- Request and response format: JSON unless the endpoint uploads media
- Auth: `Authorization: Bearer <access_token>` for protected routes
- All timestamps: ISO 8601 UTC string
- All prices: INR paise in storage and API, display as rupees in UI

## Standard Error

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Product name is required",
    "details": {
      "field": "name"
    }
  }
}
```

Common codes:

- `VALIDATION_ERROR`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_FOUND`
- `AI_SERVICE_UNAVAILABLE`
- `UPLOAD_FAILED`
- `INTERNAL_ERROR`

## 1. Health

### `GET /api/v1/health`

Used by frontend and deployment checks.

Response:

```json
{
  "status": "ok",
  "service": "kalasetu-api",
  "version": "0.1.0"
}
```

## 2. Auth

For SIH prototype, OTP can be mocked or console-logged in development.

### `POST /api/v1/auth/request-otp`

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
  "expires_in_seconds": 300
}
```

### `POST /api/v1/auth/verify-otp`

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
  "user": {
    "id": "usr_001",
    "name": "Sita Devi",
    "phone": "+919999999999",
    "role": "artisan",
    "preferred_language": "hi"
  }
}
```

## 3. Artisan Profile

### `GET /api/v1/me`

Response:

```json
{
  "id": "usr_001",
  "name": "Sita Devi",
  "phone": "+919999999999",
  "role": "artisan",
  "preferred_language": "hi",
  "cluster": "Lucknow Chikankari SHG",
  "craft_categories": ["textile", "embroidery"]
}
```

### `PATCH /api/v1/me`

Request:

```json
{
  "name": "Sita Devi",
  "preferred_language": "hi",
  "cluster": "Lucknow Chikankari SHG",
  "craft_categories": ["textile", "embroidery"]
}
```

Response: same shape as `GET /api/v1/me`.

## 4. Product Drafts

### `POST /api/v1/catalog/drafts`

Creates a draft before AI processing is complete.

Request:

```json
{
  "craft_category": "textile",
  "local_language": "hi",
  "initial_notes": "Hand embroidered cotton dupatta"
}
```

Response:

```json
{
  "id": "draft_001",
  "status": "draft",
  "craft_category": "textile",
  "local_language": "hi",
  "created_at": "2026-08-28T17:30:00Z",
  "updated_at": "2026-08-28T17:30:00Z"
}
```

### `GET /api/v1/catalog/drafts`

Response:

```json
{
  "items": [
    {
      "id": "draft_001",
      "status": "ai_ready",
      "title_hi": "हाथ की कढ़ाई वाला कॉटन दुपट्टा",
      "title_en": "Hand Embroidered Cotton Dupatta",
      "thumbnail_url": "https://example.com/media/img_001_thumb.jpg",
      "price_min_paise": 85000,
      "price_max_paise": 120000,
      "updated_at": "2026-08-28T17:40:00Z"
    }
  ]
}
```

### `GET /api/v1/catalog/drafts/{draft_id}`

Response:

```json
{
  "id": "draft_001",
  "status": "ai_ready",
  "craft_category": "textile",
  "fields": {
    "product_type": "dupatta",
    "material": "cotton",
    "technique": "hand embroidery",
    "color": "white",
    "dimensions": "2.5 m x 1 m",
    "quantity_available": 3,
    "production_time_days": 5,
    "care": "gentle hand wash"
  },
  "listing": {
    "title_hi": "हाथ की कढ़ाई वाला कॉटन दुपट्टा",
    "title_en": "Hand Embroidered Cotton Dupatta",
    "description_hi": "सफेद कॉटन पर हाथ से की गई सुंदर कढ़ाई वाला दुपट्टा।",
    "description_en": "A white cotton dupatta with detailed hand embroidery, suitable for everyday and festive wear.",
    "tags": ["cotton dupatta", "hand embroidery", "chikankari"]
  },
  "media": {
    "original_image_url": "https://example.com/media/img_001_original.jpg",
    "enhanced_image_url": "https://example.com/media/img_001_enhanced.jpg"
  },
  "pricing": {
    "suggested_min_paise": 85000,
    "suggested_max_paise": 120000,
    "confidence": "medium",
    "reasons": [
      "Material cost entered by artisan",
      "Similar cotton dupatta benchmark",
      "Manual labour time estimate"
    ]
  }
}
```

### `PATCH /api/v1/catalog/drafts/{draft_id}`

Frontend uses this after artisan edits AI-generated fields.

Request:

```json
{
  "fields": {
    "quantity_available": 2,
    "dimensions": "2.4 m x 1 m"
  },
  "listing": {
    "title_en": "Hand Embroidered Chikankari Cotton Dupatta"
  }
}
```

Response: same shape as `GET /api/v1/catalog/drafts/{draft_id}`.

### `POST /api/v1/catalog/drafts/{draft_id}/approve`

Request:

```json
{
  "approved_price_paise": 95000,
  "approval_note": "Artisan confirmed title, photo and price"
}
```

Response:

```json
{
  "id": "cat_001",
  "draft_id": "draft_001",
  "status": "approved",
  "public_share_id": "share_abc123",
  "created_at": "2026-08-28T17:50:00Z"
}
```

## 5. Media And Image Enhancement

### `POST /api/v1/catalog/drafts/{draft_id}/images`

Multipart form-data:

- `image`: product image file
- `image_type`: `product`

Response:

```json
{
  "image_id": "img_001",
  "original_image_url": "https://example.com/media/img_001_original.jpg",
  "status": "uploaded"
}
```

### `POST /api/v1/images/{image_id}/enhance`

Request:

```json
{
  "background": "neutral",
  "crop_style": "marketplace_square",
  "preserve_original": true
}
```

Response:

```json
{
  "image_id": "img_001",
  "enhanced_image_url": "https://example.com/media/img_001_enhanced.jpg",
  "quality_checks": {
    "lighting": "ok",
    "blur": "ok",
    "background_removed": true
  }
}
```

## 6. Voice And Catalog AI

### `POST /api/v1/catalog/drafts/{draft_id}/voice-notes`

Multipart form-data:

- `audio`: voice note file
- `language`: `hi`

Response:

```json
{
  "voice_note_id": "voice_001",
  "status": "uploaded"
}
```

### `POST /api/v1/catalog/drafts/{draft_id}/generate-listing`

Runs transcription, translation, field extraction and listing generation.

Request:

```json
{
  "voice_note_id": "voice_001",
  "image_id": "img_001",
  "target_languages": ["hi", "en"]
}
```

Response:

```json
{
  "draft_id": "draft_001",
  "status": "needs_confirmation",
  "transcript": {
    "language": "hi",
    "text": "यह सफेद कॉटन का दुपट्टा है, हाथ की चिकनकारी कढ़ाई है।"
  },
  "extracted_fields": {
    "product_type": {
      "value": "dupatta",
      "confidence": 0.94
    },
    "material": {
      "value": "cotton",
      "confidence": 0.88
    },
    "technique": {
      "value": "chikankari embroidery",
      "confidence": 0.81
    }
  },
  "missing_fields": ["dimensions", "quantity_available", "production_time_days"]
}
```

## 7. Pricing Assistant

### `POST /api/v1/catalog/drafts/{draft_id}/pricing/suggest`

Request:

```json
{
  "material_cost_paise": 30000,
  "labour_hours": 8,
  "hourly_rate_paise": 5000,
  "packaging_cost_paise": 5000,
  "benchmark_category": "cotton_dupatta"
}
```

Response:

```json
{
  "draft_id": "draft_001",
  "suggested_min_paise": 85000,
  "suggested_max_paise": 120000,
  "recommended_paise": 95000,
  "confidence": "medium",
  "breakdown": {
    "minimum_sustainable_price_paise": 75000,
    "market_reference_low_paise": 80000,
    "market_reference_high_paise": 140000
  },
  "reasons": [
    "Minimum cost includes material, labour and packaging",
    "Benchmark category has limited comparable products",
    "Final price can be manually changed by artisan"
  ],
  "source_date": "2026-08-28"
}
```

## 8. Share Cards

### `GET /api/v1/share/{public_share_id}`

Public buyer-facing page data.

Response:

```json
{
  "catalog_id": "cat_001",
  "title": "Hand Embroidered Chikankari Cotton Dupatta",
  "description": "A white cotton dupatta with detailed hand embroidery.",
  "image_url": "https://example.com/media/img_001_enhanced.jpg",
  "price_paise": 95000,
  "artisan": {
    "display_name": "Sita Devi",
    "cluster": "Lucknow Chikankari SHG"
  },
  "enquiry_enabled": true
}
```

### `POST /api/v1/share/{public_share_id}/enquiries`

Request:

```json
{
  "buyer_name": "Aarav Retail",
  "buyer_phone": "+918888888888",
  "message": "Interested in 20 pieces"
}
```

Response:

```json
{
  "enquiry_id": "enq_001",
  "status": "received"
}
```

## Frontend Mocking Notes

Amarjit can build with hardcoded mock JSON matching the response shapes above. When your backend is ready, he should only need to replace mock functions with `fetch()` calls.

Suggested frontend service functions:

- `requestOtp(phone)`
- `verifyOtp(requestId, otp)`
- `getDrafts()`
- `createDraft(payload)`
- `uploadDraftImage(draftId, file)`
- `enhanceImage(imageId, options)`
- `uploadVoiceNote(draftId, file, language)`
- `generateListing(draftId, payload)`
- `suggestPrice(draftId, payload)`
- `approveDraft(draftId, payload)`
- `getShareCard(publicShareId)`
