# Phase 4 Code Review: Frontend Architecture, State, Components & UI/UX

## 1. Executive Summary

Phase 4 audits the React 18 frontend architecture (`frontend/src/`), component design, state management (`HouseholdContext`), query caching (`@tanstack/react-query`), virtualized scrolling (`@tanstack/react-virtual`), theme system (`ThemeProvider`), and internationalization (`react-i18next`).

The frontend demonstrates a polished, responsive user experience with glassmorphism design accents, smooth Framer Motion animations, interactive ECharts / Recharts visualizations, and full Dark/Light theme switching. However, key technical debt exists: an oversized 1,050-line `api/client.ts` monolith, hardcoded Danish strings violating the i18n rule in `.agents/AGENTS.md`, and completely absent frontend automated tests causing `npm test` to exit with failure.

---

## 2. Architecture & Component Modularity

### 2.1 Monolithic API Client (`frontend/src/api/client.ts`)
- **Current State:** `frontend/src/api/client.ts` is **1,053 lines long**.
- **Issues:**
  - It mixes low-level `fetch` request wrappers, TypeScript model interfaces, query string serialization, and React Query custom hooks (`useTransactions`, `useBudgets`, `useAccounts`, `useBankConnections`, etc.) in a single file.
  - Module-level variables `let accessToken = ''` and `let currentHouseholdId = ''` are mutated globally.
- **Refactoring Target:** Split into:
  - `frontend/src/api/http.ts`: Base fetch wrapper with auth & `X-Household-Id` header injection.
  - `frontend/src/api/types/`: Domain interfaces (`transactions.ts`, `accounts.ts`, `budgets.ts`, `households.ts`).
  - `frontend/src/features/<domain>/api/`: Domain-specific React Query hooks (e.g. `features/transactions/useTransactions.ts`).

---

### 2.2 State Management & Household Context (`HouseholdContext.tsx`)
- **Strengths:**
  - Automatically restores selected household from `localStorage`.
  - Clears domain queries upon switching households (`queryClient.resetQueries({ predicate: ... })`) to prevent stale data flashing and cross-tenant data leakage.
- **Weakness:**
  - Mutates global module variable `setHouseholdId(id)`. If queries execute during initial mount before `useEffect` fires, requests may be sent without `X-Household-Id`, causing fallback to the user's first household.

---

### 2.3 Virtualization & Rendering Performance (`TransactionsPage.tsx`)
- Uses `@tanstack/react-virtual` with dynamic height measurement (`measureElement`).
- Flattens date group headers and transaction rows into a single indexed list for $O(1)$ DOM element rendering, handling 500+ transactions smoothly at 60 FPS.
- Smooth Framer Motion transitions for bulk-selection toolbars and category change confirmation dialogs.

---

## 3. i18n & Localization Compliance

### 3.1 Mandate:
Per `.agents/AGENTS.md`:
> 🔴 **i18n:** All UI text must be routed through `react-i18next`. The app must support `da` and `en`.

### 3.2 Violations & Hardcoded Strings Found:
1. **`TransactionsPage.tsx` (Lines 197–224):**
   ```typescript
   const isDa = i18n.language === 'da';
   let text = isDa ? `Viser ${txCount}...` : `Showing ${txCount}...`;
   ```
   *Issue:* Manual ternary branching on `i18n.language` instead of parameterized `t('transactions.filter_summary', { count: txCount, ... })`.
2. **`TransactionsPage.tsx` (Line 318):**
   - Hardcoded `"Vælg alle"` (Select all) in table header.
3. **`TransactionsPage.tsx` (Line 428):**
   - Hardcoded `"poster valgt"` (transactions selected) in bulk action bar.
4. **`TransactionsPage.tsx` (Lines 457–468):**
   - Hardcoded `"Husk denne fremover?"` and `"Nej tak"` in rule creation modal.
5. **`BudgetsPage.tsx` (Lines 103, 128):**
   - Hardcoded `" kr. / md"` and `" kr."` currency suffix without respecting active locale.
6. **Hardcoded Locale in Date Formatting:**
   - `totalAmount.toLocaleString('da-DK', ...)` hardcodes `'da-DK'` even when the user selects English (`en`).

---

## 4. Theming & Styling Architecture

- **Theme Engine (`ThemeProvider.tsx` & `index.css`):**
  - Uses CSS custom properties (`--bg-primary`, `--bg-secondary`, `--text-primary`, `--brand-primary`, `--border-color`) in HSL tailored color palettes.
  - Supports `light`, `dark`, and `system` modes with seamless persistence in `localStorage`.
- **CSS Architecture:**
  - Uses Vanilla CSS tokens combined with Tailwind utility classes.
  - Responsive layouts: collapsible sidebar navigation on desktop, sticky bottom navigation on mobile with safe-area padding.

---

## 5. Frontend Automated Testing

### Current Status:
- `frontend/package.json` specifies `"test": "vitest run"`.
- Running `npm test` output:
  ```
  No test files found, exiting with code 1
  ```
- There are **zero unit or component tests** in `frontend/src/`.
- Per project rules, E2E tests with **Playwright** are recommended for critical user journeys (login, transaction categorization, budget updates, household switching).

---

## 6. Phase 4 Refactoring Action Plan

1. **Decompose `api/client.ts`:**
   - Break 1,053-line file into domain-specific API clients and feature hooks under `src/features/` and `src/api/`.
2. **Eliminate All Hardcoded Strings & Manual Locale Checks:**
   - Add missing keys to `da.json` and `en.json`.
   - Replace `isDa ? ... : ...` in `TransactionsPage.tsx` and currency formatting with locale-aware helpers.
3. **Initialize Frontend Testing Framework:**
   - Add Vitest component smoke tests for `CategoryPicker`, `TransactionFilters`, and `MonthGrid`.
   - Configure Playwright E2E configuration in `frontend/e2e/` testing critical user flows.
