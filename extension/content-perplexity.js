// extension/content-perplexity.js
// Captures SIGNALS from Perplexity — not raw query text.

const sentKeys = new Set();

function postFeedEvent(payload) {
  chrome.runtime.sendMessage({ type: "PL_FEED_EVENT", payload }, () => {});
}

function send(signals) {
  if (!signals) return;
  const key = signals.slice(0, 60);
  if (sentKeys.has(key)) return;
  sentKeys.add(key);

  postFeedEvent({
    source: "perplexity",
    content_type: "session_signals",
    content: `[perplexity] ${signals}`,
    author: "user",
    url: window.location.href,
    timestamp: Date.now(),
  });
}

function scan() {
  const extract = window.__plExtractSignals;
  if (!extract) return;

  const selectors = [
    '[class*="UserMessage"]',
    '[data-testid="user-message"]',
    '[class*="query"] p',
  ];

  for (const sel of selectors) {
    document.querySelectorAll(sel).forEach((el) => {
      const text = el.innerText?.trim();
      if (text) send(extract(text));
    });
  }

  // URL query param
  const q = new URLSearchParams(window.location.search).get("q");
  if (q) send(extract(q));
}

scan();
new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
