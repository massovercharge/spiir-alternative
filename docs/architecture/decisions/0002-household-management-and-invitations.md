# 2. Household Management and Member Invitations

* Status: accepted
* Date: 2026-07-22

## Context and Problem Statement

Peng supports multi-tenant economics via Households. Users need the ability to custom name/rename their active households and invite members by email. Previously, invitations required the invited user to already exist in the database before an invitation could be sent, causing 404 errors if an email was not yet registered.

## Decision Drivers

* Users should be able to invite any family member or partner by email regardless of whether they have already logged into Peng.
* Household owners must be able to rename their households freely.
* All UI text must strictly comply with i18n (`da` and `en`).

## Considered Options

1. **Require pre-registration**: Block invitations until the invited user registers.
2. **Pending User Provisioning & Automatic Linkage**: Create a pending User entry upon invitation, and automatically resolve/link `logto_id` when the user signs in with matching email.

## Decision Outcome

Option 2 was chosen:
* Added `update_household` endpoint (`PATCH /api/households/{household_id}`) to rename households.
* `invite_member` provisions a pending `User` entry (`logto_id="pending:{email}"`) if the user does not exist yet.
* `_sync_user_and_household` updates the user's `logto_id` and links them to the invited household upon first login.
* Frontend settings UI updated with full i18n support and release notes updated to `v1.1.0`.
