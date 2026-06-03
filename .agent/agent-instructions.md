# Agent Instructions for Æblegården

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
- Always indicate where in the app the change has an effect (e.g., "På Byttebrættet kan du nu...").
- Keep explanations short and formatted as bullet points (array elements).

## Versioning Structure (Semantic Versioning)
We use Semantic Versioning (SemVer). The source of truth for the version is `frontend/package.json`. 

When you add a new feature or fix:
1. Determine the version bump (Patch for fixes, Minor for features, Major for breaking changes).
2. Update the `"version"` field in `frontend/package.json`.
3. Use this new version string when creating a new object in `frontend/assets/release_notes.json`. (Do not create a new object if you are just adding a second fix to an already unreleased version bump in the current task).

**Example format (`release_notes.json`):**
```json
[
  {
    "version": "1.0.1",
    "date": "YYYY-MM-DD",
    "da": {
      "features": ["På Byttebrættet kan du nu se historik for gamle byttehandler."],
      "fixes": ["Løst et problem på indstillinger-siden, hvor teksten hoppede ved scrolling."]
    },
    "en": {
      "features": ["On the Swap Board, you can now see the history of past swaps."],
      "fixes": ["Resolved an issue on the settings page where text jumped when scrolling."]
    }
  }
]
```

**Never skip this step.** Keeping the users informed is a primary directive for this repository.

## User Manual for Business and Operational Logic

Whenever you implement or change business logic or operational logic, you **MUST** update `docs/user-manual.md` as part of the same task.

- Document the behavior in practical, user-facing language.
- Include concrete examples that show what happens in realistic cases.
- Cover timing, payment, ticket, household, admin, and operational consequences when relevant.
- Keep the manual aligned with the implemented behavior, not just the intended design.

## UI Internationalization

All user-facing UI text must support both Danish and English.

- Do not add visible hardcoded UI copy without adding matching keys in `frontend/i18n/da.js` and `frontend/i18n/en.js`.
- Buttons, modal text, alerts, labels, helper text, error fallbacks, release notes, and empty/loading states must all be covered.
- If a business rule requires a literal phrase, such as a confirmation phrase, document why it is intentionally fixed and still translate the surrounding explanation.

## Server Access and Deployment

**CRITICAL RULE:** You have SSH access to the demo deployment server.
- **Server:** `root@192.168.50.5`
- **Path:**  # fill in when known, this is the root of the repo on the server
- **Deployment process:** When asked to deploy or when pushing changes that should be tested, first sync the code using `rsync` (excluding `.git`, `node_modules`, `__pycache__`, `venv`, `web-build`), and then run the docker compose build command via SSH: `ssh root@192.168.50.5 "cd /root/aeblegryden-demo && docker compose -f docker-compose.demo.yml up -d --build [service_name]"`
- Do NOT ask for permission to sync and restart the server if the user asks you to deploy or test your changes. Just do it.

## Git Workflow
- Always make regular, discrete, and functioning commits as you progress through tasks.
- Ensure each commit represents a single logical unit of work.
- Use clear and descriptive commit messages.
