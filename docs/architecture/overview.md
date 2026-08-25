# Architecture Overview

Peng consists of a decoupled frontend and backend, with a SQLite database for persistence.

## System Components

```mermaid
graph TD
    subgraph Frontend
        UI["React SPA (Vite + TS)"]
    end

    subgraph Backend
        API["FastAPI REST API"]
        Auth["Auth Middleware"]
        PS["Posting Service"]
        CS["Category Service"]
        SS["Sync Service"]
    end

    subgraph Storage
        DB["SQLite (peng.sqlite)"]
    end

    subgraph External
        EB["Enable Banking (PSD2 AIS)"]
    end

    UI --> API
    API --> Auth
    API --> PS
    API --> CS
    API --> SS
    PS --> DB
    CS --> DB
    SS --> DB
    SS --> EB
```

## Data Model (V3)

The normalized V3 data model separates immutable bank data (Posting) from mutable user data (PostingAllocation).

```mermaid
erDiagram
    BankConnection ||--o{ Account : connects
    Account ||--o{ Posting : contains
    Payee ||--o{ Posting : receives
    Posting ||--o{ PostingAllocation : "allocates (1:N for splits)"
    Category ||--o{ PostingAllocation : categorizes
    Category ||--o{ Budget : configures
    PostingAllocation }o--o{ Tag : tagged
    CategoryOverrideLog }|--|| PostingAllocation : logs

    Posting {
        string id PK "eb:account:ref"
        string account_uid FK
        string payee_id FK
        int amount_minor "§7: øre/cents"
        string currency
        string booking_date
        string original_description
        bool is_excluded
    }

    PostingAllocation {
        string id PK
        string posting_id FK
        string category_id FK
        int amount_minor "must sum to posting"
        string note
        bool is_extraordinary
    }

    Budget {
        string id PK
        string category_id FK
        int year
        int month
        int amount_minor
        string budget_type "bill or limit"
        bool rollover
    }

    CategoryOverrideLog {
        string id PK
        string original_description
        string old_category_id
        string new_category_id
    }
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| `amount_minor: int` | Eliminates floating-point errors ([ADR-0001](decisions/0001-integer-money-storage.md)) |
| Posting vs PostingAllocation | Separates immutable bank data from mutable user categorization ([ADR-0004](decisions/0004-split-transactions-and-allocations.md)) |
| Dual-Database Architecture | Isolates core ledger from heavy receipt/Storebox ingestion payloads ([ADR-0005](decisions/0005-dual-database-kvitteringer-storage.md)) |
| Inbound Email & Storebox | Automates digital receipt ingestion and autolinking ([ADR-0003](decisions/0003-storebox-inbound-email-forwarding.md)) |
| Household Management | Multi-tenant economics and email member invitations ([ADR-0002](decisions/0002-household-management-and-invitations.md)) |
| CategoryOverrideLog | Enables offline ML training for auto-categorization |
| Pluggable auth | `AUTH_PROVIDER=none\|basic\|oidc` supports single-user and multi-user deployments |

## Data Flow

1. User initiates sync via frontend → `POST /api/sync/start`
2. Backend connects to Enable Banking PSD2 API
3. Raw transactions normalized → `Posting` rows with `amount_minor` (int)
4. Default `PostingAllocation` created for each posting (1:1)
5. User categorizes via frontend → allocation updated, override logged
6. Insights computed from Posting + Allocation data
