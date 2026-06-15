param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 7823
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendRoot = Join-Path $ProjectRoot "backend"

if (-not $env:PERSONALAYER_LOCAL_AUTH) {
    $env:PERSONALAYER_LOCAL_AUTH = "1"
}
if (-not $env:PERSONALAYER_ALLOWED_ORIGINS) {
    $env:PERSONALAYER_ALLOWED_ORIGINS = "http://127.0.0.1:7823,http://localhost:7823"
}
$env:PYTHONPATH = $BackendRoot

Set-Location $BackendRoot
python -m uvicorn interfaces.http_api:app --host $HostAddress --port $Port
