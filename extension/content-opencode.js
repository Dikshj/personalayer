// extension/content-opencode.js
// Captures prompts on OpenCode web interface (opencode.ai or app.opencode.ai).
// Also handles Cursor's web dashboard if accessed via browser.

const ENDPOINT = "http://localhost:7823/feed-event";
const seen = new Set();

function send(content, source) {
  if (!content || content.length < 10) return;
  const key = content.slice(0, 80);
  if (seen.has(key)) return;
  seen.add(key);

  fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source: source || "opencode",
      content_type: "prompt",
      content: content.slice(0, 1500),
      author: "user",
      url: window.location.href,
      timestamp: Date.now(),
    }),
  }).catch(() => {});
}

function scan() {
  // Generic user message selectors that work across most chat UIs
  const selectors = [
    '[data-role="user"]',
    '[data-message-role="user"]',
    '[data-testid="user-message"]',
    '[class*="user-message"]',
    '[class*="UserMessage"]',
    '[class*="human-message"]',
    '[class*="HumanMessage"]',
  ];

  for (const sel of selectors) {
    document.querySelectorAll(sel).forEach((el) => {
      const text = el.innerText?.trim();
      if (text && text.length > 5) send(text, detectSource());
    });
  }
}

function detectSource() {
  const host = window.location.hostname;
  if (host.includes("opencode")) return "opencode";
  if (host.includes("cursor")) return "cursor";
  if (host.includes("copilot")) return "github_copilot";
  if (host.includes("gemini")) return "gemini";
  if (host.includes("grok")) return "grok";
  return "llm";
}

scan();

const observer = new MutationObserver(() => scan());
observer.observe(document.body, { childList: true, subtree: true });
