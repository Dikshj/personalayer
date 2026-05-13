param(
    [string]$TaskName = "PersonaLayer Daemon"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
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

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Runs the local PersonaLayer context daemon on login." `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName

Write-Host "PersonaLayer daemon registered and started."
Write-Host "Dashboard: http://127.0.0.1:7823/dashboard/"
Write-Host "Status:    http://127.0.0.1:7823/daemon/status"

