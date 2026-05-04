// extension/content-perplexity.js
// Captures search queries and follow-up prompts on Perplexity.ai.
// Perplexity = intent-rich signal (research queries, not casual browsing).

const ENDPOINT = "http://localhost:7823/feed-event";
const seen = new Set();

function send(content) {
  if (!content || content.length < 5) return;
  const key = content.slice(0, 80);
  if (seen.has(key)) return;
  seen.add(key);

  fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source: "perplexity",
      content_type: "query",
      content: content.slice(0, 1500),
      author: "user",
      url: window.location.href,
      timestamp: Date.now(),
    }),
  }).catch(() => {});
}

function scanQueries() {
  // Perplexity: user queries in the thread
  const selectors = [
    '[class*="UserMessage"]',
    '[data-testid="user-message"]',
    'textarea[placeholder*="Ask"]',
    '[class*="query"] p',
  ];

  for (const sel of selectors) {
    const els = document.querySelectorAll(sel);
    els.forEach((el) => {
      const text = el.innerText?.trim() || el.value?.trim();
      if (text) send(text);
    });
  }

  // Also capture from URL — Perplexity puts query in URL for direct links
  const params = new URLSearchParams(window.location.search);
  const q = params.get("q") || params.get("query");
  if (q) send(q);
}

scanQueries();

// Watch for new queries in ongoing threads
const observer = new MutationObserver(() => scanQueries());
observer.observe(document.body, { childList: true, subtree: true });

// SPA navigation (Perplexity is a SPA)
let lastUrl = location.href;
new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    setTimeout(scanQueries, 1000);
  }
}).observe(document, { subtree: true, childList: true });
