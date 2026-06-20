# PersonaLayer Local Daemon Setup

The local daemon runs on your own computer at `http://127.0.0.1:7823`.
It receives browser extension, SDK, and local collector events, stores local data in SQLite, and exposes scoped context back to PersonaLayer.

## Windows Install

1. Download `install-personalayer-daemon-windows.ps1` from the Capture page.
2. Open PowerShell.
3. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-personalayer-daemon-windows.ps1
```

4. Open:

```text
http://127.0.0.1:7823/daemon/status
```

You should see `status: ok`.

## What It Installs

- PersonaLayer backend runtime
- Local HTTP daemon on `127.0.0.1:7823`
- Windows Scheduled Task named `PersonaLayer Daemon`
- Local dashboard at `http://127.0.0.1:7823/dashboard/`

## Data Flow

```text
Browser extension / local app / SDK
  -> local daemon
  -> local SQLite and derived signals
  -> PersonaLayer app shows allowed metadata and profile signals
```

The daemon is the local collector runtime. The web app is the control center.

## Stop Or Remove

Open Task Scheduler and disable or delete `PersonaLayer Daemon`.

To remove files, delete:

```text
%LOCALAPPDATA%\PersonaLayer\daemon
```

