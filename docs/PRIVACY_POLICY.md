# Personal Layer — Privacy Policy

Effective Date: 2026-05-18

## What Personal Layer Does

Personal Layer is a **local-first personal context system**. It observes your app usage patterns, calendar events, email metadata, and other signals to build a **private behavioral profile** that lives on your device. This profile can then be shared with AI assistants and apps you trust, so they understand your preferences without you having to explain them repeatedly.

## What Stays Local

The following data **never leaves your device** unless you explicitly export it:

- **Raw event payloads** from apps, extensions, and connectors (stored in the encrypted local vault)
- **Synthesized behavioral profiles** (personas, knowledge graphs, temporal chains)
- **Embedding vectors** produced by the on-device Core ML model
- **Query logs** (audit trail of which apps requested what context)
- **Domain approvals** and **privacy boundaries**

All of the above is encrypted at rest using AES-256-GCM with a key derived from your device's Secure Enclave or OS keychain.

## What Goes to the Cloud

Our thin cloud backend (Supabase) stores **only metadata** required for identity, developer registry, and push routing:

| Cloud Table | Purpose | Contains Behavioral Data? |
|-------------|---------|---------------------------|
| `developers` | Developer registry | No |
| `apps` | App metadata and domain | No |
| `api_keys` | API key hashes and prefixes | No |
| `app_permissions` | Consent grants (scopes, active/inactive) | No |
| `push_tokens` | APNs device tokens for notifications | No |
| `notification_routes` | Notification scheduling metadata | No |

**We never store raw events, persona attributes, or context bundles in the cloud.**

## What Apps Can Receive

When an app requests your context bundle, it receives only:

- **Abstract behavioral attributes** (e.g., "prefers dark mode", "frequent traveler")
- **Active context labels** (e.g., "deep_work", "commute")
- **Feature usage patterns** (e.g., "uses_spreadsheets_daily")

Apps **do not** receive:
- Raw event payloads
- Specific email contents
- Passwords, tokens, or payment card numbers
- Exact locations or timestamps

This filtering happens automatically on your device before any data leaves the local daemon.

## Your Controls

- **Consent**: You approve which apps can access which context layers.
- **Revocation**: You can revoke an app's access at any time via the dashboard or iOS app.
- **Privacy Boundaries**: You can block specific domains or data types.
- **Deletion**: You can hard-delete all local data (Settings → Delete All Data). This removes everything from your device and invalidates cloud consent records.

## Data Retention

- Local raw events: retained for **90 days** by default, then auto-deleted.
- Knowledge graph nodes: retained indefinitely until you delete them.
- Cloud metadata: retained until you delete your account.

## Contact

For privacy questions or data deletion requests, contact: privacy@personallayer.dev
