# User-Required Production Inputs

These items cannot be completed with local code alone because they require real accounts, deployed infrastructure, or physical devices.

## OAuth Connectors

Required from you:
- Google Cloud OAuth client for Gmail, Calendar, YouTube, and Google Drive.
- Notion OAuth app credentials.
- Spotify OAuth app credentials.
- Redirect URIs for local development and production.
- Test accounts with representative data.

Environment variables:
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `NOTION_OAUTH_CLIENT_ID`
- `NOTION_OAUTH_CLIENT_SECRET`
- `SPOTIFY_OAUTH_CLIENT_ID`
- `SPOTIFY_OAUTH_CLIENT_SECRET`

## Supabase Production

Required from you:
- Supabase project URL.
- Supabase anon key.
- Supabase service role key for deployment only.
- Confirmation that migrations can be applied to the production project.

Checks to run with real Supabase:
- Apply migrations in `supabase/migrations`.
- Verify RLS on developer registry, API keys, encrypted summary blobs, sync devices, sync conflicts, observability events, push tokens, and notification routes.
- Verify Edge Functions do not log raw persona data, prompts, memory content, connector payloads, or notification payloads.

## iOS Production

Required from you:
- Apple Developer Team ID.
- App bundle ID.
- APNs key/certificate.
- TestFlight access.
- A real iPhone for background refresh and silent push testing.

Checks to run on device:
- GRDB migrations on fresh install and upgrade.
- Core ML model loading.
- App group storage.
- Background refresh.
- Silent APNs wakeups.
- Encrypted sync snapshot import/export.

## Cross-Device Encryption

Required from you:
- Decide pairing UX: QR code, one-time code, or account-mediated device approval.
- Provide at least two real devices for end-to-end testing.

Current code supports:
- Device records with `pending`, `trusted`, and `revoked` states.
- Encrypted summary blobs.
- Conflict detection and resolution.
- QR/one-time-code pairing session creation.
- X25519 public-key exchange metadata.
- X25519 + AES-GCM encrypted transfer envelopes for summary payloads.
- Pairing approval, polling, claim/import, key rotation, and recovery revoke reference endpoints.

Still needs production client work:
- Native/mobile UI for QR scanning and one-time-code entry.
- Secure platform key storage on every client.
- End-to-end testing across two physical devices.
- User-facing recovery policy copy for lost or revoked devices.

## Browser Extension Production Testing

Required from you:
- Chrome profile for loading unpacked extension.
- Domains to test approval and denial flows against.
- Decision on extension distribution: local-only, Chrome Web Store, or enterprise/private distribution.

Checks to run:
- `CL_GET_BUNDLE`
- `CL_TRACK`
- Domain approval/denial
- Raw-data leakage checks in extension logs, network requests, and native bridge messages.
