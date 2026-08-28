# KalaSetu AI Two-Person Development Workflow

This is the working agreement for building the backend and frontend in parallel without leaving integration until the end.

## Team Ownership

| Area | Primary owner | Required reviewer |
| --- | --- | --- |
| FastAPI backend, database, storage, and AI orchestration | Avnish | Amarjit for API usability |
| Flutter app, screens, state, and API client | Amarjit | Avnish for contract usage |
| `docs/API_CONTRACT.md` | Shared decision; Avnish maintains | Both must approve breaking changes |
| `.env.example`, root tooling, CI, and shared config | Person making the change | Other teammate |
| End-to-end integration | Both | Both |

Ownership means the owner makes the final conflict resolution in that area after understanding the other person's change. It does not prevent review or contributions.

## The Four Rules

1. Keep `main` runnable. Do not push feature work directly to it.
2. Use one short-lived branch and one pull request per feature.
3. Build frontend mocks and backend responses from `docs/API_CONTRACT.md`.
4. Integrate every vertical slice as soon as it is usable; do not wait for all backend or all frontend work to finish.

The shared MVP journey is:

```text
request OTP -> verify OTP -> create draft -> upload image -> upload voice
-> generate listing -> confirm fields -> suggest price -> approve -> share
```

## Day-Zero Agreement

Before feature coding, both teammates:

- Read `docs/API_CONTRACT.md`, this workflow, and `.env.example`.
- Confirm Flutter for the client and FastAPI/Python for the backend.
- Agree on the MVP journey and the features explicitly deferred by the contract.
- Review and freeze API contract version `0.2.0`.
- Confirm each local app can start and that the frontend can reach `GET /api/v1/health`.
- Enable GitHub branch protection for `main` when repository settings allow it.

Recommended `main` protection:

- Require a pull request before merging.
- Require one approval.
- Dismiss stale approval after new commits.
- Require conversation resolution.
- Block force pushes and deletion.
- Add backend and frontend test checks as soon as CI exists.

With only two teammates, the author must never approve their own PR.

## Repository Layout

Keep ownership boundaries visible. The exact generated folders may vary, but use this shape:

```text
backend/                 Avnish
  app/
  tests/
frontend/                Amarjit
  lib/
  test/
docs/
  API_CONTRACT.md        shared contract
  TEAM_WORKFLOW.md       shared process
  BACKEND_TASKS.md       backend plan
.env.example             shared configuration reference
```

Do not move or rename the other person's top-level folder without discussing it first.

## Branches

Branch names describe ownership and one deliverable:

```text
backend/setup
backend/auth
backend/catalog-drafts
backend/media-upload
backend/listing-generation
backend/pricing
backend/share

frontend/setup
frontend/auth
frontend/catalog-drafts
frontend/media-capture
frontend/listing-review
frontend/pricing
frontend/share

integration/auth
integration/catalog-flow
docs/api-contract-v1
```

Rules:

- Create a new branch from current `main`.
- One person owns and pushes to a feature branch.
- Do not reuse a merged branch for the next feature.
- Delete merged branches on GitHub.
- Keep PRs small enough to review in one sitting, preferably below about 400 changed code lines excluding generated files.
- A branch may contain its tests and required contract update; those are part of the same feature.

## Starting A Feature

First make sure there are no uncommitted changes:

```bash
git status
```

Then update `main` and create the branch:

```bash
git switch main
git pull --ff-only origin main
git switch -c backend/catalog-drafts
```

Amarjit uses the matching `frontend/...` name for his work. Replace the example branch name; do not create all branches in advance.

## While Working

Commit one understandable unit at a time:

```bash
git status
git add backend/app backend/tests docs/API_CONTRACT.md
git diff --staged
git commit -m "Add catalogue draft endpoints"
git push -u origin backend/catalog-drafts
```

Prefer targeted `git add` paths over `git add .` so secrets, local media, and unrelated files are not committed accidentally.

Before opening or updating a PR, bring in current `main`:

```bash
git fetch origin
git merge origin/main
```

Merge `main` into a published branch rather than force-pushing rewritten history. If a branch is private to its owner and has not been reviewed yet, rebasing is acceptable, but never force-push a branch the other teammate is using.

## Contract-First Feature Loop

Every feature follows the same loop:

1. Avnish proposes the route, fields, statuses, and errors in `docs/API_CONTRACT.md`.
2. Amarjit checks whether the shape supports the intended screens and states.
3. Both approve the contract change before depending on it.
4. Amarjit adds typed models and fixture-based mocks matching the contract.
5. Avnish implements the route and contract tests.
6. Avnish marks the route `mocked` or `ready` in the contract.
7. Amarjit switches the API client from fixture to HTTP.
8. Both test the full slice together and merge its integration PR.

Example:

```text
Contract: POST /catalog/drafts/{draft_id}/pricing/suggest
Frontend: pricing form + loading/error/result states using the contract fixture
Backend: calculation + validation + standard errors
Integration: real HTTP call, version handling, and artisan override
```

The frontend may begin immediately after step 3. It does not wait for step 5.

## API Client And Mock Rules

Amarjit keeps networking behind one client layer:

```text
screen -> controller/state -> repository/service -> API client or fixture source
```

- Screens never construct endpoint paths or parse raw error bodies.
- Request and response models use the same field names and nullability as the contract.
- All mocks live in reusable fixture files; do not duplicate JSON inside widgets.
- Mock and real implementations expose the same methods.
- One config flag selects mock or real mode.
- Unknown response fields are ignored.
- Access tokens and private values use secure device storage, not source code.
- User-facing labels are translated in the app; API enum values stay unchanged.

Avnish keeps FastAPI models and OpenAPI aligned with the same contract:

- Reuse response schemas instead of returning ad hoc dictionaries.
- Override FastAPI validation errors with the documented error shape.
- Add contract tests for status codes, required fields, enum values, and nullability.
- Never return a provider-specific AI payload directly to the frontend.

## Local Integration Networking

The backend binds to `0.0.0.0:8000`. The frontend base URL depends on where Flutter runs:

| Flutter target | Development API origin |
| --- | --- |
| Android emulator | `http://10.0.2.2:8000` |
| iOS simulator on the same Mac | `http://127.0.0.1:8000` |
| Flutter web on the same Mac | `http://localhost:8000` |
| Physical phone on the same Wi-Fi | `http://<Avnish-Mac-LAN-IP>:8000` |

Pass the value locally, for example:

```bash
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
```

Never commit a teammate's LAN IP. For a deployed demo, use one HTTPS API URL. Camera, microphone, and secure-origin behavior must be tested on a physical device before the SIH demo.

## Pull Request Standard

PR title examples:

```text
Backend: add catalogue draft CRUD
Frontend: add catalogue capture flow
Integration: connect catalogue flow to API
Docs: freeze API contract v0.2.0
```

Every PR description contains:

```markdown
## What changed

## Contract impact
- None / additive / behavioral / breaking
- Endpoints:

## How to test

## Evidence
- Test output, screenshot, or sample request/response

## Known limitations
```

Merge requirements:

- The owner has reviewed their own diff.
- Automated checks pass.
- The required reviewer approves.
- Contract changes are called out explicitly.
- No real `.env`, credentials, phone lists, private media, database files, or generated build artifacts are included.
- Use squash merge for feature PRs so `main` stays readable.

After merge:

```bash
git switch main
git pull --ff-only origin main
git branch -d backend/catalog-drafts
```

Delete only your own local branch after confirming the PR is merged.

## Definition Of Done

Backend feature:

- Method, path, auth, status codes, body, and errors match the contract.
- OpenAPI documents the route.
- Happy path and important failure paths have automated tests.
- Ownership checks prevent cross-user access.
- Retries do not create duplicates where idempotency is required.
- Mock provider behavior is deterministic and clearly labelled.

Frontend feature:

- Uses typed request and response models from the contract.
- Works with contract fixtures.
- Loading, empty, validation, offline, retry, and expired-session states are handled where relevant.
- API calls are isolated from widgets.
- No secret or fixed developer URL is committed.
- Layout, permissions, and input behavior work on the target Android device.

Integrated feature:

- Works against the real backend with no screen-level mock remaining.
- Auth header, multipart upload, status polling, null fields, and standard errors work.
- A retry does not duplicate the operation.
- Both teammates run the acceptance path.
- The result is merged into and still runnable from `main`.

## Integration Checkpoints

Merge and verify in this order:

| Checkpoint | Backend result | Frontend result | Joint proof |
| --- | --- | --- | --- |
| 0. Setup | Health route, config, CORS, tests | App shell, config, API client | Device displays backend connected |
| 1. Auth | Request/verify OTP and profile | Login and profile screens | Login survives app navigation |
| 2. Drafts | Create/list/get/update | Draft list and editor | Create and edit one real draft |
| 3. Media | Image and voice upload | Camera/gallery/microphone flow | Real files appear on the draft |
| 4. Generation | Async operation and generated fields | Polling and confirmation UI | Voice produces editable bilingual draft |
| 5. Pricing | Range, reasons, and source metadata | Cost inputs and override UI | Price can be suggested and changed |
| 6. Approval/share | Immutable catalogue, public share, enquiry | Approval, share page, enquiry form | Buyer enquiry reaches backend |

Do not begin the next checkpoint with both people if the previous joint proof is broken on `main`. One teammate can continue isolated work while the other fixes the checkpoint.

## Daily Rhythm

At the start of a work session:

- Pull current `main`.
- Say which branch and files each person expects to touch.
- Confirm any contract decision needed that day.
- Choose one integration checkpoint to advance.

Before stopping:

- Push work in progress to the owner's feature branch.
- Update the PR with test steps and current limitations.
- Tell the other teammate whether each touched endpoint is `planned`, `mocked`, `ready`, or `blocked`.
- Do not leave undocumented local-only schema or environment changes.

A five-minute written update is enough:

```text
Branch:
Completed:
Contract changes:
Ready for teammate:
Blocked by:
Next:
```

## Shared-File Rule

Discuss before both people edit any of these:

- `docs/API_CONTRACT.md`
- `.env.example`
- Database migrations or shared data models
- Root dependency or lock files
- Routing/navigation configuration
- CI workflows

If both features require the same shared file, agree who edits it first. Merge that small prerequisite PR, then both branches update from `main`.

## Conflict Procedure

When a merge reports conflicts:

1. Stop and run `git status`.
2. Read both versions; never choose all of one side blindly.
3. Ask the primary file owner when intent is unclear.
4. Resolve only the listed files and remove conflict markers.
5. Run relevant formatters, tests, and the affected app flow.
6. Stage the resolved files and commit the merge.
7. Push and tell the reviewer what was resolved.

Useful checks:

```bash
git status
rg '^(<<<<<<<|=======|>>>>>>>)' .
git diff --check
```

Never use `git reset --hard`, force push, or delete someone else's branch as a conflict shortcut.

## Contract Change Rule

Once contract version `0.2.0` is frozen:

- Additive optional fields are normally safe, but still require documentation and review.
- A rename, removal, type change, new required field, path change, or semantic change is breaking.
- For a breaking change, update both sides in one agreed integration window or keep the old behavior temporarily.
- Record every merged contract change in the API contract change log.
- Never announce a route as `ready` until its behavior and OpenAPI match the contract.

When frontend and backend disagree, the merged API contract wins until both approve a new change.

## Current Starting Point

First, Avnish completes the setup and contract work on:

```bash
git switch backend/setup
```

Avnish opens the setup PR, Amarjit reviews the API shapes from a frontend point of view, and both freeze contract version `0.2.0`. After that PR is merged, Amarjit starts from the updated `main`:

```bash
git switch main
git pull --ff-only origin main
git switch -c frontend/setup
```

The first shared success is deliberately small:

1. Backend serves `GET /api/v1/health`.
2. Flutter receives its API base URL through `--dart-define`.
3. Flutter calls the real route through its API client.
4. Both test Android emulator and one physical phone.
5. Setup PRs merge before auth work begins.
