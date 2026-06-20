param(
    [string]$InstallDir = "$env:LOCALAPPDATA\PersonaLayer\daemon",
    [string]$RepoZipUrl = "https://github.com/Dikshj/personalayer/archive/refs/heads/master.zip",
    [string]$TaskName = "PersonaLayer Daemon"
)

$ErrorActionPreference = "Stop"

function Require-Command($Name, $InstallHint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required. $InstallHint"
    }
}

Write-Host "PersonaLayer daemon installer"
Write-Host "Install directory: $InstallDir"

Require-Command "python" "Install Python 3.10+ from https://www.python.org/downloads/windows/"

$TempRoot = Join-Path $env:TEMP ("personalayer-daemon-" + [Guid]::NewGuid().ToString("N"))
$ZipPath = Join-Path $TempRoot "personalayer.zip"
$ExtractDir = Join-Path $TempRoot "extract"

New-Item -ItemType Directory -Path $TempRoot, $ExtractDir -Force | Out-Null
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

Write-Host "Downloading PersonaLayer runtime..."
Invoke-WebRequest -Uri $RepoZipUrl -OutFile $ZipPath

Write-Host "Extracting..."
Expand-Archive -Path $ZipPath -DestinationPath $ExtractDir -Force
$RepoRoot = Get-ChildItem $ExtractDir -Directory | Select-Object -First 1
if (-not $RepoRoot) {
    throw "Could not find extracted PersonaLayer repo."
}

Write-Host "Copying runtime files..."
Copy-Item -Path (Join-Path $RepoRoot.FullName "*") -Destination $InstallDir -Recurse -Force

$BackendDir = Join-Path $InstallDir "backend"
if (-not (Test-Path $BackendDir)) {
    throw "Backend directory was not found after install."
}

Write-Host "Installing Python dependencies..."
Push-Location $BackendDir
python -m pip install -r requirements.txt --quiet
Pop-Location

$Python = (Get-Command python).Source
$Action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "-m uvicorn main:app --host 127.0.0.1 --port 7823" `
    -WorkingDirectory $BackendDir

$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Days 365)

Write-Host "Registering Windows login task..."
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Runs the local PersonaLayer context daemon on login." `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName

Write-Host ""
Write-Host "PersonaLayer daemon installed and started."
Write-Host "Status:    http://127.0.0.1:7823/daemon/status"
Write-Host "Dashboard: http://127.0.0.1:7823/dashboard/"
Write-Host ""
Write-Host "Next: open PersonaLayer > Capture and click Refresh."

