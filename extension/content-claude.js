// extension/content-claude.js
// Captures user prompts sent to Claude.ai (web interface).
// Only captures USER messages — not Claude's responses.

const ENDPOINT = "http://localhost:7823/feed-event";
const seen = new Set();

function send(content) {
  if (!content || content.length < 10) return;
  const key = content.slice(0, 80);
  if (seen.has(key)) return;
  seen.add(key);

  fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source: "claude",
      content_type: "prompt",
      content: content.slice(0, 1500),
      author: "user",
      url: window.location.href,
      timestamp: Date.now(),
    }),
  }).catch(() => {});
}

function scanMessages() {
  // Claude.ai: user messages in human turn containers
  const selectors = [
    '[data-testid="user-message"]',
    '.font-user-message',
    '[class*="human-turn"] p',
    '[class*="HumanTurn"] p',
  ];

  for (const sel of selectors) {
    const els = document.querySelectorAll(sel);
    if (!els.length) continue;
    els.forEach((el) => {
      const text = el.innerText?.trim();
      if (text) send(text);
    });
    break; // found working selector
  }

  // Fallback: find by structure — user messages sit above AI responses
  // Claude wraps user turns in a div with specific padding pattern
  document.querySelectorAll('[class*="human"]').forEach((el) => {
    const text = el.innerText?.trim();
    if (text && text.length > 10 && text.length < 3000) send(text);
  });
}

scanMessages();

const observer = new MutationObserver(() => scanMessages());
observer.observe(document.body, { childList: true, subtree: true });
