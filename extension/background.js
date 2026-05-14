chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "CL_GET_BUNDLE") {
    fetch("http://127.0.0.1:7432/v1/context/bundle")
      .then(r => r.json())
      .then(data => sendResponse({success: true, bundle: data}))
      .catch(e => sendResponse({success: false, error: e.message}));
    return true;
  }
  if (request.action === "CL_TRACK") {
    fetch("http://127.0.0.1:7432/v1/ingest/extension", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({event_type: request.event_type, payload: request.payload})
    })
      .then(r => r.json())
      .then(data => sendResponse({success: true}))
      .catch(e => sendResponse({success: false, error: e.message}));
    return true;
  }
});
