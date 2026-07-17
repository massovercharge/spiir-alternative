# Peng

> Self-hostable personal finance — categorization, budgeting & accounting with bank integration.

Peng is an open-source alternative to [Spiir](https://spiir.dk) designed for self-hosting. It connects to your bank via [Enable Banking](https://enablebanking.com), automatically imports transactions, and helps you categorize, budget, and understand your personal finances.

## Features

- 🏦 **Bank sync** via Enable Banking (PSD2/AIS) — works with any supported European bank
- 🏷️ **Smart categorization** — rule-based + ML-assisted transaction categorization
- 📊 **Budget tracking** — consumption limits, fixed bills, and rollover
- 📈 **Insights** — income/expense trends, category breakdowns, anomaly detection
- 🐳 **Self-hostable** — single `docker compose up` for your own private instance
- 🌐 **i18n** — Danish and English UI from day one
- 🔒 **Privacy-first** — your financial data stays on your server

## Quick Start (Docker)

```bash
git clone https://github.com/massovercharge/peng.git
cd peng
docker compose up
```

Open `http://localhost:8080` in your browser.

## Quick Start (Development)

```bash
# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,test]"
uvicorn app.api:app --app-dir backend --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

See [docs/guides/development.md](docs/guides/development.md) for the full development setup guide.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────────────┐
│   Frontend   │────▶│   Peng API   │────▶│   Enable Banking  │
│  React + TS  │     │   FastAPI    │     │   (PSD2 / AIS)    │
└─────────────┘     └──────┬───────┘     └───────────────────┘
                           │
                    ┌──────▼───────┐
                    │    SQLite    │
                    │  (peng.db)   │
                    └──────────────┘
```

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture Overview](docs/architecture/overview.md) | System design and data flow |
| [Development Guide](docs/guides/development.md) | Local setup and contribution workflow |
| [Enable Banking Setup](docs/guides/enable-banking.md) | Bank connectivity configuration |
| [Self-Hosting Guide](docs/guides/self-hosting.md) | Docker deployment for end users |
| [Contributing](CONTRIBUTING.md) | How to contribute |
| [ADR Index](docs/architecture/decisions/) | Architecture Decision Records |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_PROVIDER` | `none` | Auth mode: `none`, `basic`, `oidc` |
| `PENG_DATA_DIR` | `./data` | Root directory for database and bank data |
| `ENABLEBANKING_APP_ID` | — | Enable Banking application ID |
| `ENABLEBANKING_PRIVATE_KEY_PATH` | — | Path to RSA private key PEM |
| `ENABLEBANKING_REDIRECT_URL` | — | OAuth redirect URL for bank consent |
| `PENG_AUTH_USERNAME` | `admin` | Username for basic auth |
| `PENG_AUTH_PASSWORD` | — | Password for basic auth (required when `AUTH_PROVIDER=basic`) |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, SQLModel, SQLite |
| Frontend | TypeScript, React 18, Vite |
| Auth | Pluggable (none / basic / OIDC) |
| Bank Sync | Enable Banking (PSD2 AIS) |
| Deployment | Docker Compose |

## License

[AGPL-3.0](LICENSE) — free to use, modify, and self-host. Contributions welcome.
