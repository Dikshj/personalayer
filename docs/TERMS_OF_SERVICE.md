# Personal Layer Terms of Service

Effective date: 2026-06-06

These Terms govern use of Personal Layer software, hosted services, local runtimes, SDKs, extensions, and developer APIs. If you do not agree to these Terms, do not use Personal Layer.

This document is production-ready operating language for launch. It should be reviewed by counsel before broad commercial distribution or regulated use.

## 1. The Service

Personal Layer is a local-first personal context system. It collects and derives user-controlled context on a user's device and shares scoped context bundles with apps only when authorized.

The service may include local apps, browser extensions, mobile apps, SDKs, developer APIs, and thin cloud infrastructure for account metadata, app registry, permissions, device pairing, push routing, and optional encrypted sync.

## 2. Eligibility And Accounts

You must be legally able to enter into these Terms. You are responsible for keeping account credentials, device credentials, API keys, and local session tokens secure. You must promptly revoke access if a credential or device is lost, exposed, or compromised.

## 3. User Data Ownership

Users own their personal data and context. Personal Layer does not sell user context, train foundation models on user context, or disclose raw local data except as directed by the user, required to operate authorized features, or required by law.

You are responsible for the legality of the data you connect, import, process, sync, export, or share through Personal Layer.

## 4. Privacy And Retention

Use of Personal Layer is also governed by the [Privacy Policy](PRIVACY_POLICY.md) and [Data Retention Policy](DATA_RETENTION.md). Users can revoke app access and delete local context. Cloud account and permission metadata is retained only as needed to operate the service, meet security needs, or satisfy legal obligations.

## 5. Developer Responsibilities

Developers building with Personal Layer must:

- Request only the minimum scopes required for the product feature.
- Clearly disclose what context layers are accessed and why.
- Respect consent denial, revocation, and scope changes immediately.
- Treat context bundles as confidential user data.
- Not persist session-only bundles beyond the active session.
- Not attempt to re-identify, reconstruct, or infer raw private content from derived context.
- Not use Personal Layer to build spyware, surveillance, unauthorized employee monitoring, or credential harvesting tools.
- Maintain reasonable security controls for API keys, logs, caches, and downstream processors.
- Delete cached user context on user request or when no longer needed for the stated purpose.

## 6. Acceptable Use

You may not use Personal Layer to:

- Collect, share, or infer data from someone without lawful consent.
- Bypass privacy boundaries, permissions, rate limits, app verification, or security controls.
- Upload malware, exploit code, or abusive automation.
- Process data in a way that violates applicable law or third-party terms.
- Build systems that make high-stakes decisions about employment, credit, housing, insurance, healthcare, criminal justice, or legal rights without appropriate human review, disclosure, and legal compliance.

## 7. Security

You must report suspected vulnerabilities to security@personallayer.dev and avoid public disclosure until we have had a reasonable opportunity to investigate and remediate. See [Security Policy](SECURITY.md).

## 8. Third-Party Services

Personal Layer may connect to third-party services such as email, calendar, GitHub, Notion, Spotify, YouTube, Google services, Supabase, cloud hosting providers, and AI APIs. Those services are governed by their own terms and privacy policies. Personal Layer is not responsible for third-party services outside our control.

## 9. Availability And Changes

Personal Layer may change, suspend, or discontinue features as the product evolves. Hosted services may experience downtime, maintenance, or capacity limits. Continued use after updated Terms are published means you accept the updated Terms.

## 10. Disclaimers

Personal Layer is provided "as is" and "as available" without warranties of any kind to the maximum extent permitted by law. We do not warrant that the service will be uninterrupted, error-free, secure against every threat, or suitable for every regulated use case.

## 11. Limitation Of Liability

To the maximum extent permitted by law, Personal Layer and its operators are not liable for indirect, incidental, consequential, special, exemplary, or punitive damages, or for lost profits, lost data, business interruption, or unauthorized third-party conduct.

## 12. Termination

You may stop using Personal Layer at any time. We may suspend or terminate access if you violate these Terms, create security risk, create legal risk, or misuse the service. After termination, users may request deletion of cloud account metadata where legally and operationally permitted.

## 13. Contact

Legal notices: legal@personallayer.dev

Privacy requests: privacy@personallayer.dev

Security reports: security@personallayer.dev
