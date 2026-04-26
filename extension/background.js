// extension/background.js
const ENDPOINT = "http://localhost:7823/event";

// tabData[tabId] = { url, title, startTime }
const tabData = {};

// When user switches to a tab, record start time
chrome.tabs.onActivated.addListener(({ tabId, previousTabId }) => {
  if (previousTabId !== undefined) {
    flushTab(previousTabId);
  }
  chrome.tabs.get(tabId, (tab) => {
    if (chrome.runtime.lastError || !tab) return;
    tabData[tabId] = {
      url: tab.url || "",
      title: tab.title || "",
      startTime: Date.now(),
    };
  });
});

// When a page finishes loading in a tab, reset its timer
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete") return;
  if (!tab.url || isSkipped(tab.url)) return;
  tabData[tabId] = {
    url: tab.url,
    title: tab.title || "",
    startTime: Date.now(),
  };
});

// When a tab closes, flush it
chrome.tabs.onRemoved.addListener((tabId) => {
  flushTab(tabId);
  delete tabData[tabId];
});

function isSkipped(url) {
  return (
    url.startsWith("chrome://") ||
    url.startsWith("chrome-extension://") ||
    url.startsWith("about:") ||
    url.startsWith("http://localhost") ||
    url.startsWith("http://127.0.0.1")
  );
}

function flushTab(tabId) {
  const data = tabData[tabId];
  if (!data || !data.url || isSkipped(data.url)) return;

  const timeSpent = Math.floor((Date.now() - data.startTime) / 1000);
  if (timeSpent < 3) return; // skip flash navigations

  fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: data.url,
      title: data.title,
      time_spent_seconds: timeSpent,
      timestamp: Date.now(),
    }),
  }).catch(() => {
    // Server not running — silently ignore
  });
}
