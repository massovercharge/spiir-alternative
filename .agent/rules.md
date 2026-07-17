# Agent Instructions for spiir-alternative

You are an AI coding assistant working on the spiir-alternative repository. Always follow these rules.

## Updating Release Notes (Nyheder & Opdateringer)

**CRITICAL RULE:** Whenever you implement a bug fix or a new feature, you **MUST** update `frontend/assets/release_notes.json` as your final step.

The `release_notes.json` file is a self-contained array of update objects.

1. Find the object for the current version (e.g., `"version": "1.0.0"`) or create a new one if it's a new version.
2. Under the `"da"` key, append your fix/feature in Danish to the `"fixes"` or `"features"` array.
3. Under the `"en"` key, append your fix/feature in English to the `"fixes"` or `"features"` array.

**Guidelines for texts:**
- Texts MUST be non-technical and written from the user's perspective.
- Focus on what the user is interested in knowing and how it impacts them.
- Always indicate where in the app the change has an effect (e.g., "På overblikket kan du nu...").
- Keep explanations short and formatted as bullet points (array elements).

## Versioning Structure (Semantic Versioning)
We use Semantic Versioning (SemVer). The source of truth for the version is `frontend/package.json`. 

When you add a new feature or fix:
1. Determine the version bump (Patch for fixes, Minor for features, Major for breaking changes).
2. Update the `"version"` field in `frontend/package.json`.
3. Use this new version string when creating a new object in `frontend/assets/release_notes.json`. (Do not create a new object if you are just adding a second fix to an already unreleased version bump in the current task).

## User Manual for Business and Operational Logic

Whenever you implement or change business logic or operational logic, you **MUST** update `docs/user-manual.md` as part of the same task.

- Document the behavior in practical, user-facing language.
- Include concrete examples that show what happens in realistic cases.
- Cover bank synchronization, categorisation, and operational consequences when relevant.
- Keep the manual aligned with the implemented behavior, not just the intended design.

## UI Internationalization

All user-facing UI text must support both Danish and English.

- Do not add visible hardcoded UI copy without adding matching keys in the frontend internationalization files.
- Buttons, modal text, alerts, labels, helper text, error fallbacks, release notes, and empty/loading states must all be covered.
- If a business rule requires a literal phrase, such as a confirmation phrase, document why it is intentionally fixed and still translate the surrounding explanation.

## Theme-Driven UI and Dynamic Language

**CRITICAL RULE:** All visual UI elements must be theme-driven, and all user-facing text must be served through the app's internationalization layer.

- The frontend must support both light and dark mode and should follow the user's device preference by default via `prefers-color-scheme`, while still allowing an explicit app-level theme override when implemented.
- Do not hardcode component colors, chart colors, borders, shadows, or background surfaces directly in feature components. Use shared design tokens/CSS variables so pages, tables, charts, modals, buttons, and form controls switch cleanly between light and dark themes.
- New visual work must be implemented in a way that can be expressed by semantic tokens such as background, surface, panel, border, text, muted text, accent, success, warning, and danger.
- Plotly/canvas/SVG/chart styling must also be theme-aware. Chart backgrounds, grid lines, axis labels, legends, hover labels, and series colors must not be left in a fixed light-only or dark-only style.
- All visible strings must come from the i18n layer and support dynamic language switching between Danish and English. This includes chart titles, axis labels, legends, table headers, filter labels, tooltips, button labels, placeholders, loading text, empty states, errors, release notes, and modal copy.
- Do not add new visible hardcoded Danish or English strings in React components unless you are also creating the proper i18n keys and using the translation helper/hook at the call site.
- When touching legacy UI that still has hardcoded strings or fixed colors, prefer moving the touched area toward theme tokens and i18n instead of adding more one-off styling or copy.

## Server Access and Deployment

**CRITICAL RULE:** You have SSH access to the deployment server.
- **Server:** `root@192.168.50.5`
- **Path:** `/root/spiir-alternative`
- **Deployment process:** When asked to deploy or when pushing changes that should be tested, run the deployment script: `./scripts/deploy.sh`
- Do NOT ask for permission to run the deployment script if the user asks you to deploy or test your changes. Just do it.

## Git Workflow
- Always make regular, discrete, and functioning commits as you progress through tasks.
- Ensure each commit represents a single logical unit of work.
- Use clear and descriptive commit messages.

## Handling Sensitive Financial Data
**CRITICAL RULE:** This repository processes real personal banking data via Enable Banking.
- Never commit the `data/` directory, `.env` files, or `.pem` keys to git.
- **NEVER** print or output real transaction data, account numbers, or balances into the chat logs or artifacts. Always mock data if you need to show an example.
- Ensure the `ENABLEBANKING_PRIVATE_KEY_PATH` and `LOGTO` variables remain secure.

## Architecture Boundaries
- **Backend:** Python / FastAPI. All business logic, bank fetching, and Logto JWT validation (`auth.py`) happens here.
- **Frontend:** React / Vite. Uses `@logto/react` for authentication. Do not add Next.js/SSR concepts.
- **Routing:** Cloudflare handles ingress routing directly to the frontend Nginx container on port `25432`, which in turn proxies `/api` to the backend. Do not introduce Traefik configurations.

## Financial Engineering & Operational Directives

### 1. Currency Precision & Math
**Constraint:** Never use standard `float` data types for currency math.
**Rule:** Always use Python's `decimal.Decimal` module or integer-based 'cents' (e.g., `1050` instead of `10.50`) for all monetary calculations, aggregations, and database storage to avoid catastrophic floating-point rounding errors.

### 2. Append-Only Ledger Integrity
**Constraint:** Design databases to treat transactions as immutable history.
**Rule:** Never implement `UPDATE` or `DELETE` SQL endpoints for core transaction rows. To correct a mistake, implement reversing/offsetting transactions (double-entry bookkeeping) or use a separate 'Overrides' table that applies patches dynamically on read.

### 3. Idempotent Data Synchronization
**Constraint:** Ensure bank synchronization logic is idempotent.
**Rule:** All bank import logic must use upserts (e.g., `INSERT ON CONFLICT DO NOTHING`) based on a deterministic, unique hash of the transaction's bank ID, date, and amount to prevent double-counting income if a sync overlaps or fails.

### 4. Defensive API Polling & Caching
**Constraint:** Aggressively respect external rate limits.
**Rule:** Never call external bank APIs directly from a UI render cycle. Always implement aggressive server-side caching, background job queues, and exponential backoff for network failures to prevent IP bans or revoked banking sessions.

### 5. Automated Data Sanitization
**Constraint:** Be self-reliant at generating fake data for UI iteration.
**Rule:** When building or iterating on frontend React components, always create robust, deterministic mock data generators so UI components can be tested in isolation without risking exposure of real banking data.
