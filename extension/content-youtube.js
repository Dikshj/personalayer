// extension/content-youtube.js
// Captures YouTube: what the user watches + what's recommended to them.
// Signals: interests, entertainment habits, learning topics.

const ENDPOINT = "http://localhost:7823/feed-event";
const seen = new Set();

function send(payload) {
  fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, timestamp: Date.now() }),
  }).catch(() => {});
}

// ── Watch page: capture the video being watched ──
function captureWatchPage() {
  if (!window.location.pathname.startsWith("/watch")) return;

  const titleEl =
    document.querySelector("h1.ytd-watch-metadata yt-formatted-string") ||
    document.querySelector("#title h1") ||
    document.querySelector("h1.title");

  if (!titleEl) return;
  const title = titleEl.innerText.trim();
  if (!title || seen.has(title)) return;
  seen.add(title);

  const channelEl =
    document.querySelector("#channel-name a") ||
    document.querySelector(".ytd-channel-name a");
  const author = channelEl ? channelEl.innerText.trim() : "";

  send({
    source: "youtube",
    content_type: "watch",
    content: title,
    author,
    url: window.location.href,
  });
}

// ── Home/feed: capture recommended videos ──
function captureRecommended(root) {
  const selectors = [
    "ytd-rich-item-renderer #video-title",
    "ytd-video-renderer #video-title",
    "ytd-compact-video-renderer #video-title",
  ];

  for (const sel of selectors) {
    const items = root.querySelectorAll ? root.querySelectorAll(sel) : [];
    items.forEach((el) => {
      const title = el.innerText?.trim();
      if (!title || seen.has(title)) return;
      seen.add(title);

      const card = el.closest("ytd-rich-item-renderer, ytd-video-renderer, ytd-compact-video-renderer");
      const channelEl = card?.querySelector("#channel-name, .ytd-channel-name");
      const author = channelEl ? channelEl.innerText.trim() : "";
      const linkEl = card?.querySelector("a#thumbnail, a[href*='/watch']");
      const url = linkEl ? "https://www.youtube.com" + linkEl.getAttribute("href") : window.location.href;

      send({
        source: "youtube",
        content_type: "recommended",
        content: title,
        author,
        url,
      });
    });
  }
}

// Initial capture
captureWatchPage();
captureRecommended(document);

// Watch for SPA navigation + lazy content
const observer = new MutationObserver((mutations) => {
  captureWatchPage();
  for (const m of mutations) {
    m.addedNodes.forEach((node) => {
      if (node.nodeType !== 1) return;
      captureRecommended(node);
    });
  }
});

observer.observe(document.body, { childList: true, subtree: true });

// YouTube is a SPA — re-run on URL changes
let lastUrl = location.href;
new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    seen.clear(); // reset per-page dedup
    setTimeout(captureWatchPage, 1500); // wait for DOM to settle
  }
}).observe(document, { subtree: true, childList: true });
