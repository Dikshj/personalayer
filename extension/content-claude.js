// extension/content-claude.js
// Captures SIGNALS from Claude.ai — not raw prompt text.

const ENDPOINT = "http://localhost:7823/feed-event";
const sentKeys = new Set();

function send(signals) {
  if (!signals) return;
  const key = signals.slice(0, 60);
  if (sentKeys.has(key)) return;
  sentKeys.add(key);

  fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source: "claude",
      content_type: "session_signals",
      content: `[claude] ${signals}`,
      author: "user",
      url: window.location.href,
      timestamp: Date.now(),
    }),
  }).catch(() => {});
}

function scan() {
  const extract = window.__plExtractSignals;
  if (!extract) return;

  const selectors = [
    '[data-testid="user-message"]',
    '[class*="human-turn"] p',
    '[class*="HumanTurn"] p',
    '[class*="human"] p',
  ];

  for (const sel of selectors) {
    document.querySelectorAll(sel).forEach((el) => {
      const text = el.innerText?.trim();
      if (text && text.length > 10) send(extract(text));
    });
  }
}

scan();
new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
