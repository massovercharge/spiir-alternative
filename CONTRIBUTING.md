# Contributing to Peng

First off, thanks for taking the time to contribute!

## Code of Conduct
This project is open-source, and we expect contributors to be respectful and constructive.

## Development Workflow
1. Fork the repo and create your branch from `main`.
2. Follow the setup in `docs/guides/development.md`.
3. If you've added code that should be tested, add tests.
4. If you've changed APIs, update the documentation.
5. Ensure the test suite passes (`pytest backend/tests/` and `npm test`).
6. Make sure your code lints (`ruff check backend/`).

## Pull Requests
- Use [Conventional Commits](https://www.conventionalcommits.org/) for your PR title (e.g. `feat: add budget rollover`).
- Keep PRs small and focused on a single issue.
- Describe *why* you made the change, not just *what* you changed.
