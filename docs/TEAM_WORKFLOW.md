# Two-Person Git Workflow

Team:

- Avnish: backend
- Amarjit: frontend

Goal: both people work simultaneously without breaking each other's work.

## Main Rule

Do not push directly to `main`.

Use feature branches, pull requests and small merges.

## Branch Ownership

Avnish backend branches:

- `backend/auth`
- `backend/catalog-api`
- `backend/media-upload`
- `backend/voice-ai`
- `backend/pricing`
- `backend/share-card`

Amarjit frontend branches:

- `frontend/auth-screens`
- `frontend/catalog-flow`
- `frontend/camera-upload`
- `frontend/voice-flow`
- `frontend/pricing-ui`
- `frontend/share-page`

## Daily Start

Both people should run:

```bash
git checkout main
git pull origin main
```

Then create or update their feature branch:

```bash
git checkout -b backend/catalog-api
```

or:

```bash
git checkout backend/catalog-api
git rebase origin/main
```

## Commit And Push

```bash
git status
git add .
git commit -m "Add catalog draft endpoints"
git push -u origin backend/catalog-api
```

## Pull Request Rules

- One feature per PR.
- PR title should say what is ready.
- The other teammate reviews before merge.
- If the PR changes `docs/API_CONTRACT.md`, mention it clearly.
- After merge, both people pull latest `main`.

## Avoiding Merge Chaos

- Avnish owns backend folders and API docs.
- Amarjit owns frontend screens and UI components.
- Discuss before changing shared files like:
  - `package.json`
  - `.env.example`
  - routing config
  - API contract
  - database schema
  - shared TypeScript types

## Contract-First Workflow

For every feature:

1. Avnish writes or updates the endpoint in `docs/API_CONTRACT.md`.
2. Amarjit builds UI with mock JSON from the contract.
3. Avnish implements the backend route.
4. Amarjit replaces mock service with real `fetch()` call.
5. Both test that one user flow works.

Example:

```text
Feature: pricing assistant
Avnish: POST /api/v1/catalog/drafts/{draft_id}/pricing/suggest
Amarjit: pricing screen using mock response
Integration: connect screen to backend endpoint
```

## Definition Of Done

Backend PR is done when:

- Endpoint exists.
- Request and response match `docs/API_CONTRACT.md`.
- Validation errors use the standard error shape.
- Swagger docs show the route.
- At least one happy path has been tested.

Frontend PR is done when:

- Screen works with mock data.
- Loading, empty and error states exist.
- API service function is isolated in one place.
- UI does not depend on random backend field names.
- Mobile layout is usable.

Integration PR is done when:

- Frontend calls the real backend endpoint.
- Auth token, request body and response mapping work.
- Error message displays correctly.
- No mock data remains in that user flow unless intentionally kept for demo fallback.

## Merge Conflict Rule

If a conflict happens:

- Do not panic.
- Identify who owns the conflicted file.
- The owner resolves it while preserving the other person's intended change.
- Run the app after resolving.
- Commit the conflict resolution with a clear message.

## Recommended PR Order

1. `backend/auth` and `frontend/auth-screens`
2. `backend/catalog-api` and `frontend/catalog-flow`
3. `backend/media-upload` and `frontend/camera-upload`
4. `backend/voice-ai` and `frontend/voice-flow`
5. `backend/pricing` and `frontend/pricing-ui`
6. `backend/share-card` and `frontend/share-page`

Backend and frontend can happen at the same time. The API contract is what keeps them aligned.
