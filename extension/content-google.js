// extension/content-google.js
// Captures Google search result titles.
// Background.js already captures the query via URL params.
// This adds: which results appeared → richer interest signal.

const seen = new Set();

function send(payload) {
  chrome.runtime.sendMessage({ type: "PL_FEED_EVENT", payload: { ...payload, timestamp: Date.now() } }, () => {});
}

function captureResults() {
  // Extract current query
  const params = new URLSearchParams(window.location.search);
  const query = params.get("q") || "";
  if (!query) return;

  // Organic result titles — h3 inside .yuRUbf or [data-ved]
  const resultEls = document.querySelectorAll("h3");
  const titles = [];

  resultEls.forEach((h3) => {
    const text = h3.innerText.trim();
    if (!text || seen.has(text)) return;
    seen.add(text);

    const linkEl = h3.closest("a");
    const url = linkEl ? linkEl.href : "";
    titles.push({ text, url });
  });

  if (!titles.length) return;

  // Send as one feed item: query + result titles
  send({
    source: "google",
    content_type: "search_results",
    content: `Query: ${query}\nResults: ${titles.map(t => t.text).join(" | ")}`,
    author: "",
    url: window.location.href,
  });
}

// Run after page settles
setTimeout(captureResults, 1000);

// Handle SPA navigation (Google Instant)
let lastUrl = location.href;
new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    setTimeout(captureResults, 800);
  }
}).observe(document, { subtree: true, childList: true });
