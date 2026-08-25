# 3. Storebox / Nexi Inbound Email Forwarding and Receipt Ingestion

* Status: accepted
* Date: 2026-08-24

## Context and Problem Statement

Storebox (now Nexi) allows users to request an export copy of their digital receipt data sent to their email. This email contains a time-limited download link pointing to a ZIP archive containing JSON receipt files. Users want to simply forward this email to their household in Peng, have Peng download and extract the ZIP idempotently, link receipt items to bank transactions, and maintain an audit log of received emails and their processing status.

## Decision Drivers

* **Zero user setup**: End users should simply copy their household's forwarding email address and forward the Storebox export email.
* **Flexible self-hosting**: Self-hosters can choose between autonomous IMAP mailbox polling (`INBOUND_EMAIL_IMAP_ENABLED=true`) or inbound webhook forwarding (e.g. via Cloudflare Email Workers, SendGrid, Postmark, Mailgun, or custom reverse proxy).
* **Robust Link Extraction**: Parse both HTML `<a>` tags and plain text URLs, handle HTML entity decoding (e.g. `&amp;` in AWS S3 presigned URLs), and prioritize expiring download links.
* **Idempotency & Auto-linking**: Prevent duplicate receipts using composite unique keys and autolink receipts to matching bank transactions.
* **Auditability & Observability**: Maintain a database log of inbound emails (`InboundEmail`) with status, timestamps, and error diagnostics, and expose retry endpoints.
* **Security & Isolation**: Multi-tenant household token resolution ensuring receipt data is strictly confined to the targeted household.

## Decision Outcome

1. **Database Models**:
   * Added `inbound_email_token` column to `Household` with auto-migration and automatic backfill.
   * Created `InboundEmail` model tracking received emails, extraction results, deduplicated counts, and errors.
2. **Inbound Processing Service**:
   * Implemented `inbound_email_service.py` supporting RFC822 MIME payloads, JSON payloads, and direct attachments.
   * Intelligent heuristic scoring for Storebox download URLs and handling of AWS S3 presigned links.
   * Background downloading, ZIP extraction, idempotent receipt ingestion (`replace_storebox_upload`), and auto-linking (`auto_link_receipts`).
3. **IMAP & Webhook Ingestion**:
   * Background `imap_worker.py` polling for `UNSEEN` emails and marking processed messages as `\Seen`.
   * Public webhook routes `POST /api/inbound/email` and `POST /api/inbound/email/{token}`.
4. **User Interface & Settings**:
   * Updated `SettingsPage.tsx` with email address display, 1-click clipboard copy, inbound history tracking table, status badges, retry actions, and an interactive test simulation tool.
   * Added full Danish and English translations (`da` and `en`) and updated release notes for `v1.5.0`.
