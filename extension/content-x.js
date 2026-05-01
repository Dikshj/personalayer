// extension/content-x.js
// Captures tweets from X/Twitter feed as they load.
// Sends to PersonaLayer: what content the user is consuming.

const ENDPOINT = "http://localhost:7823/feed-event";
const seen = new Set();

function extractTweets(root) {
  const articles = root.querySelectorAll
    ? root.querySelectorAll("article[data-testid='tweet']")
    : [];

  articles.forEach((article) => {
    // Tweet text
    const textEl = article.querySelector("[data-testid='tweetText']");
    if (!textEl) return;
    const content = textEl.innerText.trim();
    if (!content || seen.has(content.slice(0, 80))) return;
    seen.add(content.slice(0, 80));

    // Author
    let author = "";
    const nameEl = article.querySelector("[data-testid='User-Name']");
    if (nameEl) author = nameEl.innerText.split("\n")[0].trim();

    // Tweet URL (find <a> with /status/ in href)
    let url = window.location.href;
    const links = article.querySelectorAll("a[href*='/status/']");
    if (links.length) url = "https://x.com" + links[0].getAttribute("href");

    send({ source: "x", content_type: "tweet", content, author, url });
  });
}

function send(payload) {
  fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, timestamp: Date.now() }),
  }).catch(() => {});
}

// Initial scan
extractTweets(document);

// Watch for new tweets as user scrolls
const observer = new MutationObserver((mutations) => {
  for (const m of mutations) {
    m.addedNodes.forEach((node) => {
      if (node.nodeType !== 1) return;
      extractTweets(node);
    });
  }
});

observer.observe(document.body, { childList: true, subtree: true });
