# Personal Layer Data Retention Policy

Effective date: 2026-06-06

This policy defines how long Personal Layer keeps local data, cloud metadata, operational records, and developer-facing context. It should be implemented in product defaults, backend cleanup jobs, support workflows, and developer terms before production launch.

## Retention Principles

- Keep raw personal data local by default.
- Keep only the minimum cloud metadata needed to operate the service.
- Prefer session-only sharing for app context bundles.
- Delete or anonymize data when it is no longer needed.
- Let users revoke access and delete local context without contacting support.
- Keep security records only as long as needed for abuse prevention, incident response, and legal compliance.

## Default Schedule

| Data category | Location | Default retention | Deletion trigger |
| --- | --- | --- | --- |
| Raw app, browser, and connector events | Local encrypted vault | 90 days | Automatic cleanup, user deletion, or shorter user rule |
| Derived persona signals | Local encrypted store | Until user deletion or replacement by newer signal | User deletion, confidence expiry, or profile reset |
| Local embeddings | Local encrypted store | Same as source signal or raw event | Source deletion or profile reset |
| Local query logs | Local encrypted store | 30 days | Automatic cleanup or user deletion |
| App permission grants | Cloud metadata | While account/app relationship is active | User revocation, app removal, or account deletion |
| Developer registry and app metadata | Cloud metadata | While developer account is active | Developer deletion or administrative removal |
| API key hashes and prefixes | Cloud metadata | Until key revocation plus 30 days audit window | Key revocation or account deletion |
| Device pairing records | Cloud/local metadata | Until device revocation or account deletion | Device revoke, recovery reset, or account deletion |
| Encrypted sync blobs | Cloud object/table storage | 30 days after replacement or until account deletion | Snapshot replacement, sync disablement, or account deletion |
| Push tokens and notification routes | Cloud metadata | Until device/app revoke or token expiry | App revoke, device revoke, token invalidation, or account deletion |
| Operational telemetry | Cloud logs/metrics | Up to 30 days | Scheduled deletion or incident retention hold |
| Security investigation records | Restricted security storage | As long as required for investigation and legal needs | Case closure plus legal retention window |

## Context Bundle Retention

Unless a user grants a longer-lived purpose-specific permission, apps must treat Personal Layer context bundles as session-only:

- Do not store raw bundle payloads beyond the active user session.
- Do not use bundles to create shadow profiles outside Personal Layer.
- Cache only the minimum derived feature state needed to deliver the requested feature.
- Delete cached context when consent is revoked, the session ends, or the feature no longer needs it.

## User Deletion

When a user deletes local context, production clients should:

1. Stop new context sharing immediately.
2. Delete local raw events, derived signals, embeddings, local query logs, and privacy boundaries selected by the user.
3. Revoke app permissions and device trust if the user requests account-level deletion.
4. Queue deletion of cloud metadata that is not required for security, fraud prevention, accounting, or legal compliance.
5. Return a clear completion state in the UI.

## Backup And Sync

Personal Layer cannot directly erase copies inside device backups controlled by the user's operating system or cloud backup provider. Deleted data should be removed from active app storage immediately and age out of normal backups according to the user's device backup lifecycle.

Optional cross-device sync must upload only encrypted summary blobs. Raw local events should not be uploaded for sync.

## Production Implementation Requirements

Before real users or real data enter production:

- Schedule raw-event cleanup for the 90-day default window.
- Schedule operational telemetry deletion for the 30-day default window.
- Confirm account deletion removes app permissions, push tokens, notification routes, sync metadata, and encrypted blobs.
- Confirm developer-facing docs state that context bundles are session-only unless a longer retention scope is explicitly granted.
- Confirm support can route privacy deletion requests sent to privacy@personallayer.dev.
