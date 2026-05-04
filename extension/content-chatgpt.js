// extension/content-chatgpt.js
// Captures user prompts sent to ChatGPT.
// Signal: what problems user is actively solving right now.
// Only captures USER messages — not AI responses.

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
      source: "chatgpt",
      content_type: "prompt",
      content: content.slice(0, 1500),
      author: "user",
      url: window.location.href,
      timestamp: Date.now(),
    }),
  }).catch(() => {});
}

function scanMessages() {
  // ChatGPT marks user turns with data-message-author-role="user"
  const userMsgs = document.querySelectorAll('[data-message-author-role="user"]');
  userMsgs.forEach((el) => {
    const text = el.innerText?.trim();
    if (text) send(text);
  });
}

// Scan existing messages on load
scanMessages();

// Watch for new messages as conversation continues
const observer = new MutationObserver(() => scanMessages());
observer.observe(document.body, { childList: true, subtree: true });
