# Context Handshake

Personal Layer integrations should keep a short context handshake near the
boundary between a client and the local daemon. The handshake names the caller,
the requested context surface, the retention expectation, and the current user
consent state before any source data is read.

This gives dashboard, extension, native, and SDK clients the same vocabulary for
describing why context is being requested. It also keeps privacy review focused
on a small set of fields that can be audited consistently across interfaces.

Suggested fields:

- `client_id`: stable client or integration identifier.
- `surface`: dashboard, extension, SDK, native app, or daemon job.
- `purpose`: short reason for requesting local context.
- `retention`: none, session, rolling window, or user-approved archive.
- `consent_ref`: approval record or policy version used for the request.
