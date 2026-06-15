# Personal Layer Privacy Policy

Effective date: 2026-06-06

Personal Layer is a local-first personal context system. It helps approved apps and AI assistants understand your preferences by building a private profile on your device. This policy explains what data is processed, what stays local, what limited metadata may be stored in the cloud, how long data is retained, and how to contact us.

This document is product-ready operating language for launch. It should be reviewed by counsel before broad commercial distribution or regulated use.

## Data We Process

Depending on what you enable, Personal Layer may process:

- App and browser interaction events, such as feature usage, page domains, and app identifiers.
- Connector metadata from services such as email, calendar, GitHub, Notion, Spotify, YouTube, or Google Fit.
- Derived profile signals, such as preferences, working patterns, active contexts, and skill indicators.
- Permission records, domain approvals, privacy boundaries, audit logs, device-pairing records, and sync status.
- Account and developer registry metadata needed to operate cloud-backed production services.

Personal Layer is designed to filter or block secrets, credentials, payment data, precise private content, and sensitive personal identifiers before data is shared with apps.

## What Stays Local

The following data stays on your device unless you explicitly export it, sync it to a trusted paired device, or authorize sharing with an app:

- Raw event payloads from apps, extensions, local SDKs, and connectors.
- Raw email bodies, private notes, browser page text, and local files.
- Synthesized behavioral profiles and local memory graphs.
- Embedding vectors produced by on-device models.
- Local query logs showing which apps requested context.
- Domain approvals, privacy boundaries, and local vault data.
- OAuth access and refresh tokens stored in the operating system keychain or secure storage.

Local data is encrypted at rest using AES-256-GCM where supported by the runtime. Device keys and tokens should be stored in OS keychain or Secure Enclave backed storage in production builds.

## What We Store In The Cloud

The production cloud service is intentionally thin. Supabase or equivalent production infrastructure may store:

| Category | Purpose | Behavioral content stored? |
| --- | --- | --- |
| Account identity metadata | Sign-in and account routing | No |
| Developer registry records | App registration and verification | No |
| API key hashes and prefixes | API authentication | No |
| App permission grants | Consent, scopes, status, timestamps | No raw content |
| Device and pairing metadata | Trusted device sync state | No raw content |
| Encrypted summary blobs | Optional cross-device sync | Encrypted before upload |
| Push tokens and routes | Silent notification routing | No behavioral text |
| Operational telemetry | Reliability and abuse monitoring | Redacted metadata only |

We do not sell personal data, train foundation models on your personal context, or store raw persona events in the cloud.

## How Apps Receive Context

Apps can receive context only after consent. A context bundle may include:

- Abstract preference signals.
- Active context labels.
- Coarse feature usage patterns.
- Capability, schedule, or workflow hints.
- Confidence and provenance metadata.

Apps must not receive raw connector payloads, specific email bodies, passwords, access tokens, payment card numbers, social security numbers, exact private locations, or raw browsing histories through standard Personal Layer APIs.

## Your Controls

You can:

- Approve or deny app access by scope.
- Revoke an app's access at any time.
- Disconnect integrations.
- Create privacy boundaries for fields, apps, domains, and retention limits.
- Delete individual signals where supported.
- Delete all local context data.
- Request account deletion and deletion of cloud metadata.

Revocation stops future access. Apps and developers that received context before revocation are responsible for honoring the developer terms and deleting cached data where required.

## Data Retention

Personal Layer applies the retention schedule in [Data Retention Policy](DATA_RETENTION.md). In summary:

- Raw local events are retained for 90 days by default unless the user chooses a shorter retention period.
- Session-only context bundles should not be persisted by receiving apps beyond the active session.
- Local query logs are retained for 30 days by default.
- Cloud permission and account metadata is retained while the account is active.
- Operational telemetry is retained for up to 30 days unless needed for security investigation or legal compliance.
- Deleted local context should be removed from active local storage immediately and from normal backups according to the user's device backup lifecycle.

## Security

Security controls include local encryption, OS keychain storage, scoped app permissions, RLS on cloud tables, CORS and origin checks, filtered outbound bundles, and silent push payloads without behavioral text. Security reports should be sent to security@personallayer.dev. See [Security Policy](SECURITY.md).

## International Use

Personal Layer may be used across regions. Users are responsible for enabling only integrations and deployments that comply with their local laws. Production operators should configure hosting regions, subprocessors, data-processing terms, and deletion workflows before onboarding real users.

## Children

Personal Layer is not intended for children under 13, or the minimum digital consent age in the user's jurisdiction. Do not use Personal Layer to collect context from children without appropriate consent and legal review.

## Changes

We may update this policy as the product, infrastructure, and legal requirements evolve. Material changes should be reflected by updating the effective date and publishing the revised policy before the change applies to users.

## Contact

Privacy requests: privacy@personallayer.dev

Security reports: security@personallayer.dev

Legal notices: legal@personallayer.dev
