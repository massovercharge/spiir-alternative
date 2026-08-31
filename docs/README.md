# Peng Documentation

This directory contains all project documentation, organized by audience and purpose.

## Structure

```
docs/
├── architecture/          # System design and technical decisions
│   ├── overview.md        # Architecture overview with diagrams
│   ├── data-model.md      # Database schema and ER diagrams
│   └── decisions/         # Architecture Decision Records (ADR)
├── guides/                # How-to guides for users and developers
│   ├── development.md     # Local development setup
│   ├── enable-banking.md  # Bank connectivity configuration
│   ├── coop-receipts.md   # Coop digital receipts integration & bookmarklet
│   ├── self-hosting.md    # Docker deployment guide
│   └── contributing.md    # Contribution guidelines
├── code_review/           # Phased full-stack code review & refactoring roadmap
└── reference/             # Reference material
    ├── category-taxonomy.md      # Default category structure
    └── environment-variables.md  # Complete env var reference
```

## Conventions

- All documentation is written in **English**.
- Diagrams are written as **Mermaid** in Markdown (no image files).
- Each Architecture Decision Record (ADR) follows the [template](architecture/decisions/template.md).
- API documentation is auto-generated from FastAPI's OpenAPI schema at `/docs`.
