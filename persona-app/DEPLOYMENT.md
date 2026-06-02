# Persona App Production Deployment

## Hosting Target

The production frontend target is Netlify. The repository-level `netlify.toml` builds the React/Vite app from `persona-app` and publishes `persona-app/dist`.

## Required Environment

Set these variables in Netlify before deploying:

```bash
VITE_PERSONALAYER_API_BASE=https://your-personalayer-api-origin
VITE_PERSONALAYER_REQUIRE_SESSION=1
```

Do not leave `VITE_PERSONALAYER_API_BASE` pointed at `127.0.0.1` or `localhost` for production.

## Backend Requirements

The production API must:

- Serve the PersonaLayer HTTP API over HTTPS.
- Allow the deployed frontend domain through the backend web-domain permission table.
- Accept a PersonaLayer session token in the `Authorization: Bearer ...` header, or set an equivalent `pl_session` cookie.
- Return JSON errors for unauthorized, unavailable, and empty-data states.

## Session Behavior

The app reads a session token from `VITE_PERSONALAYER_SESSION_TOKEN` first, then from browser localStorage under `personalayer_session_token`.

For production, prefer issuing a short-lived `pl_session` cookie from the API domain or giving the user a session bootstrap flow. The current deployed fallback prompts for a session token and stores it in this browser.

## Verification

Before pushing a deployment:

```bash
npm --prefix persona-app ci
npm --prefix persona-app run build
npm --prefix persona-app run preview
```

Review the deployed build in browser with:

- No session token.
- Invalid or unavailable API base.
- Empty backend data.
- Backend offline.
- Normal API responses.
