# JavaScript SDK Examples

## Feature Ranking Demo

Open `feature-ranking-demo.html` from a local server while the PersonaLayer daemon is running on `127.0.0.1:7823`.

```bash
cd sdk/javascript
python -m http.server 3002
```

Then visit:

```text
http://127.0.0.1:3002/examples/feature-ranking-demo.html
```

The demo registers an app, emits feature usage, queries PCL, and renders the feature list in the ranked order returned by the decision bundle.
