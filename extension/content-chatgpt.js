// extension/content-chatgpt.js
// Captures SIGNALS from ChatGPT — not raw prompt text.
// What stored: task type, domain, tech stack keywords only.

const ENDPOINT = "http://localhost:7823/feed-event";
const sentKeys = new Set();

function send(signals, source) {
  if (!signals) return;
  const key = signals.slice(0, 60);
  if (sentKeys.has(key)) return;
  sentKeys.add(key);

  fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source,
      content_type: "session_signals",
      content: `[${source}] ${signals}`,
      author: "user",
      url: window.location.href,
      timestamp: Date.now(),
    }),
  }).catch(() => {});
}

function scanMessages() {
  const extract = window.__plExtractSignals;
  if (!extract) return;

  document.querySelectorAll('[data-message-author-role="user"]').forEach((el) => {
    const text = el.innerText?.trim();
    if (!text) return;
    const signals = extract(text);
    if (signals) send(signals, "chatgpt");
  });
}

scanMessages();
const observer = new MutationObserver(scanMessages);
observer.observe(document.body, { childList: true, subtree: true });
