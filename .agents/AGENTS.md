# Peng Agent Rules

This directory contains instructions and rules for agents working on the Peng project.

## Project Context
- **Name:** Peng
- **Goal:** Self-hostable, bank-agnostic personal finance app inspired by Spiir.
- **Stack:** FastAPI, SQLite, React 18, Vite.

## Rules
- 🔴 **Pengebeløb:** All monetary values MUST be stored and handled as `INTEGER` representing the minor unit (e.g. øre for DKK, cents for EUR or USD). Do NOT use `float` or `DECIMAL` in the database. 
- 🔴 **i18n:** All UI text must be routed through `react-i18next`. The app must support `da` and `en`.
- **Docs:** Maintain the architecture decision records (ADRs) and `docs/` when making structural changes.
- **Commits:** Use Conventional Commits (`feat:`, `fix:`, `refactor:`, etc.).
- **Code Style:** Backend uses `ruff` (max length 100). Frontend uses `eslint` + `prettier`.
- **Git Workflow:** Commits happen directly to `main` by default. Feature branches are strictly for major refactoring or uncertain experimental features.
- **Testing Strategy:** 
  - Backend: `pytest` for integration tests of endpoints against a test DB (SQLite in-memory or file). Focus on happy paths and critical edge cases.
  - Frontend: End-to-End (E2E) testing with `Playwright`. Focus on critical user journeys. Avoid over-testing small components with unit tests to keep maintenance low.
- **Architecture & Folder Structure:**
  - Backend (`backend/`): Strict separation of concerns -> `api/` (routers), `core/` (config/setup), `models/` (DB tables), `schemas/` (Pydantic models), `services/` (business logic).
  - Frontend (`frontend/src/`): Domain-driven grouping where possible -> `components/` (reusable UI), `features/` (domain-specific logic/UI), `pages/` (routes), `services/` (API calls), `store/` (global state).
