// Personal Layer Content Script
// Injects the page marker and bridges window.postMessage <-> chrome.runtime

const CL_ORIGIN_MARKER = "data-cl-ext";

// Mark the page so the SDK knows the extension is present
document.documentElement.setAttribute(CL_ORIGIN_MARKER, "1");

// Listen for requests from the page (SDK or inline scripts)
window.addEventListener("message", (event) => {
  // Only accept messages from the same window and with our namespace
  if (event.source !== window) return;
  if (!event.data || typeof event.data !== "object") return;
  if (event.data.namespace !== "personalayer") return;

  const { type, payload, requestId } = event.data;

  // Forward to background service worker via chrome.runtime
  chrome.runtime.sendMessage(
    { type, payload, origin: window.location.origin },
    (response) => {
      // Send response back to page
      window.postMessage(
        { namespace: "personalayer", type: `${type}_response`, requestId, payload: response },
        "*"
      );
    }
  );
});

// Also handle CL_GET_BUNDLE / CL_TRACK legacy messages
window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  if (!event.data || typeof event.data !== "object") return;

  const msg = event.data;
  if (msg.type === "CL_GET_BUNDLE" || msg.type === "CL_TRACK" || msg.type === "CL_CHECK_AVAILABLE") {
    chrome.runtime.sendMessage(
      { type: msg.type, ...msg },
      (response) => {
        window.postMessage({ type: `${msg.type}_RESPONSE`, payload: response }, "*");
      }
    );
  }
});
