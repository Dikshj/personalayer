# PersonaLayer Browser Extension Setup

The browser extension sends browser-side metadata to the local daemon at `http://127.0.0.1:7823`.

## Before You Start

Install and start the local daemon first. Confirm:

```text
http://127.0.0.1:7823/daemon/status
```

returns `status: ok`.

## Load The Extension

1. Open Chrome or Edge.
2. Go to:

```text
chrome://extensions
```

3. Turn on Developer mode.
4. Click Load unpacked.
5. Select the `extension` folder from the installed PersonaLayer runtime.

Default Windows install path:

```text
%LOCALAPPDATA%\PersonaLayer\daemon\extension
```

## What It Sends

The extension sends allowed browser activity metadata to the local daemon, such as page domain, page title, supported app signals, and search/activity metadata. It should not be used to send passwords, private form values, or raw sensitive page content.

## Verify

Open the extension popup. It should show whether the daemon is reachable. Then return to PersonaLayer > Capture and click Refresh.

