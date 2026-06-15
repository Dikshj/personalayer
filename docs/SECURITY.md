# Personal Layer Security Policy

Effective date: 2026-06-06

Personal Layer is local-first and privacy-sensitive. Security reports should be sent to security@personallayer.dev.

## Supported Scope

Security reports are in scope for:

- Python FastAPI local backend.
- iOS app and local encrypted storage.
- Browser extension and native bridge.
- JavaScript and Python SDKs.
- Supabase migrations and Edge Functions.
- Device pairing, encrypted sync, consent, egress filtering, and API authentication.
- Production deployment configuration documented in this repository.

## Reporting A Vulnerability

Email security@personallayer.dev with:

- Affected component and version or commit.
- Clear reproduction steps.
- Impact and attack scenario.
- Logs, screenshots, or proof-of-concept code where useful.
- Whether the issue may expose user context, credentials, tokens, or cloud metadata.

Do not include real user personal data in reports. Use synthetic test data whenever possible.

## Safe Harbor

We will not pursue legal action for good-faith security research that:

- Avoids privacy violations, data destruction, persistence, spam, and service disruption.
- Uses only accounts, devices, and data you own or are authorized to test.
- Reports vulnerabilities promptly and privately.
- Gives us a reasonable opportunity to investigate and remediate before public disclosure.

## Response Targets

| Severity | Example | Target response |
| --- | --- | --- |
| Critical | Remote code execution, secret extraction, cloud RLS bypass exposing user metadata | 24 hours |
| High | Authentication bypass, unauthorized context bundle access, token leakage | 3 business days |
| Medium | Privacy boundary bypass, sensitive logging, cross-origin weakness | 7 business days |
| Low | Hardening issue with limited exploitability | 14 business days |

These are targets, not guarantees. We may adjust based on exploitability, impact, and operational constraints.

## Production Security Requirements

Before real users or real data enter production:

- Configure HTTPS for every hosted endpoint.
- Configure explicit CORS origins for production domains and extension origins.
- Keep cloud tables protected by row-level security.
- Store device keys and OAuth tokens in OS secure storage.
- Keep notification payloads free of behavioral text.
- Keep operational telemetry redacted.
- Rotate exposed API keys and revoke compromised device sessions.
- Run production hardening tests and Supabase RLS integration tests against the deployed environment.

## Security Contact

security@personallayer.dev

For privacy requests, use privacy@personallayer.dev. For legal notices, use legal@personallayer.dev.
