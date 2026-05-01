// extension/content-linkedin.js
// Captures LinkedIn feed posts as they load.
// Extracts: post text, author, post URL.

const ENDPOINT = "http://localhost:7823/feed-event";
const seen = new Set();

function extractPosts(root) {
  // LinkedIn uses different class names depending on version — try both
  const selectors = [
    ".feed-shared-update-v2",
    "[data-urn]",
  ];

  let posts = [];
  for (const sel of selectors) {
    const found = root.querySelectorAll ? root.querySelectorAll(sel) : [];
    if (found.length) { posts = Array.from(found); break; }
  }

  posts.forEach((post) => {
    // Post text
    const textEl =
      post.querySelector(".feed-shared-text span[dir='ltr']") ||
      post.querySelector(".update-components-text span") ||
      post.querySelector(".feed-shared-update-v2__description");
    if (!textEl) return;

    const content = textEl.innerText.trim().slice(0, 1000); // cap at 1k chars
    if (!content || seen.has(content.slice(0, 60))) return;
    seen.add(content.slice(0, 60));

    // Author
    let author = "";
    const actorEl =
      post.querySelector(".update-components-actor__name") ||
      post.querySelector(".feed-shared-actor__name");
    if (actorEl) author = actorEl.innerText.trim();

    // Post URL — LinkedIn encodes it in data-urn or in <a> links
    let url = window.location.href;
    const linkEl = post.querySelector("a[href*='/posts/'], a[href*='/feed/update/']");
    if (linkEl) url = linkEl.href;

    send({ source: "linkedin", content_type: "post", content, author, url });
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
extractPosts(document);

// Watch for lazy-loaded posts
const observer = new MutationObserver((mutations) => {
  for (const m of mutations) {
    m.addedNodes.forEach((node) => {
      if (node.nodeType !== 1) return;
      extractPosts(node);
    });
  }
});

observer.observe(document.body, { childList: true, subtree: true });
