# Phase 5 Code Review: DevOps, Deployment, CI/CD & Documentation

## 1. Executive Summary

Phase 5 investigates containerization (`Dockerfile`, `docker-compose.yml`), CI/CD and deployment scripts (`scripts/check.sh`, `scripts/deploy.sh`), Cloudflare Workers (`deploy/cloudflare/`), Architecture Decision Records (`docs/architecture/`), and semantic versioning / release note synchronization.

The deployment model utilizes Docker multi-stage builds serving the compiled React single-page app directly through FastAPI/Uvicorn, backed by persistent SQLite storage. However, critical vulnerabilities exist in deployment scripts (where test and lint failures are completely suppressed), unauthenticated Cloudflare worker webhooks, and missing ADR documentation for recent architectural changes.

---

## 2. Docker & Container Architecture

### 2.1 Multi-Stage Dockerfile (`Dockerfile`)
- **Stage 1 (Frontend Builder):** `node:22-alpine` runs `npm ci` and `npm run build`.
- **Stage 2 (Backend Runtime):** `python:3.12-slim` installs `uv` from `ghcr.io/astral-sh/uv`, installs backend dependencies in editable mode, copies static frontend assets to `/app/frontend/dist`, and serves with Uvicorn.
- **Improvements Needed:**
  - **Non-Root User:** The container runs as `root`. For production container hardening, create a dedicated `peng` system user (`useradd -u 1000 peng`) and drop privileges.
  - **Volume Ownership:** Ensure `/data` has appropriate write permissions for non-root runtime users.

### 2.2 Docker Compose (`docker-compose.yml`)
- Integrates `peng`, `logto`, and `logto-db` (Postgres 14).
- Traefik labels configured for `auth.seame.click` with IP whitelisting middleware on the Logto Admin port (`3002`).
- Safe volume mounts for `/data` and Postgres persistence (`logto-data-v3`).

---

## 3. Deployment & CI/CD Scripts

### 3.1 [CRITICAL] `scripts/check.sh` Error Suppression
In `scripts/check.sh`:
```bash
echo "Running backend lint..."
PYTHONPATH="$ROOT_DIR/backend" "$PYTHON" -m ruff check \
    "$ROOT_DIR/backend/app" \
    "$ROOT_DIR/backend/tests" 2>/dev/null || true  # ⚠️ Suppressed!

echo "Running backend tests..."
PYTHONPATH="$ROOT_DIR/backend" "$PYTHON" -m pytest "$ROOT_DIR/backend/tests" -q 2>/dev/null || true  # ⚠️ Suppressed!

echo "Building frontend..."
cd "$ROOT_DIR/frontend"
npm run build

echo "All checks passed."
```
- **Vulnerability:** `2>/dev/null || true` completely silences errors and forces a success exit code (`0`).
- If a developer or automated script runs `./scripts/deploy.sh`, `check.sh` will report `"All checks passed."` and deploy broken or untested code to the production server.

### 3.2 `scripts/deploy.sh`
- Rsyncs code directly to the remote server `192.168.50.5` excluding cache, secrets, and `node_modules`.
- Restarts containers with `docker compose up --build -d --remove-orphans`.
- Must strictly fail and abort if `./scripts/check.sh` encounters any lint or test errors.

---

## 4. Cloudflare Email Worker Integration

### `deploy/cloudflare/email-worker.js`:
- Intercepts incoming Storebox/Nexi forwarded emails in Cloudflare Email Routing.
- Extracts raw MIME stream (`message.raw`) and forwards as `POST` with `Content-Type: message/rfc822` to `https://peng.seame.click/api/inbound/email`.
- **Security Recommendation:**
  - Cloudflare worker should sign requests with an HMAC header (`X-Peng-Signature`) or send a secret bearer token (`Authorization: Bearer <INBOUND_WEBHOOK_SECRET>`) configured in `wrangler.toml` secrets.

---

## 5. Documentation, ADRs & Release Notes

### 5.1 Architecture Decision Records (`docs/architecture/decisions/`)
- Existing ADRs:
  - `0001-integer-money-storage.md`: Minor-unit integer storage rules.
  - `0002-household-management-and-invitations.md`: Multi-tenancy and invitations.
  - `0003-storebox-inbound-email-forwarding.md`: Inbound email receipt extraction architecture.
- **Missing ADRs to Create:**
  - `0004-split-transactions-and-allocations.md`: Architecture of `Posting` vs `PostingAllocation`.
  - `0005-dual-database-kvitteringer-storage.md`: Boundary between `peng.sqlite` and `kvitteringer.db`.

### 5.2 Release Notes & SemVer Alignment
- Release notes are tracked in `frontend/src/i18n/release_notes.json` and mirrored in `frontend/assets/release_notes.json`.
- Includes bilingual changelogs (`da` and `en`) up to `v1.5.3`.
- In-app release notes viewer is accessible at `/settings` under "Udgivelsesnoter" / "Release Notes".

---

## 6. Phase 5 Refactoring Action Plan

1. **Fix `scripts/check.sh`:**
   - Remove `2>/dev/null || true` and enforce strict fail-fast execution (`set -euo pipefail`).
2. **Add Cloudflare Webhook Authentication:**
   - Pass a shared secret token between `email-worker.js` and FastAPI `/api/inbound/email`.
3. **Add Missing Architecture Decision Records (ADRs):**
   - Author ADR-0004 (Posting vs PostingAllocation Split Architecture) and ADR-0005 (Dual-Database Isolation).
4. **Harden Docker Container:**
   - Add non-root system user to `Dockerfile` runtime stage.
