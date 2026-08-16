# Build (if needed) and run the FinAlly container. Safe to run repeatedly.
param([switch]$Build)

$ErrorActionPreference = "Stop"

$Image = "finally:latest"
$Container = "finally"
$Root = Split-Path -Parent $PSScriptRoot
$Url = "http://localhost:8000"

if ($Build -or -not (docker images -q $Image)) {
    Write-Host "Building $Image ..."
    docker build -t $Image $Root
}

if (docker ps -q -f "name=^$Container$") {
    Write-Host "FinAlly is already running at $Url"
    exit 0
}

docker rm -f $Container 2>$null | Out-Null

$EnvArgs = @()
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    $EnvArgs = @("--env-file", $EnvFile)
} else {
    Write-Host "No .env found at $EnvFile - starting with simulator market data and no LLM key."
}

$DbDir = Join-Path $Root "db"
New-Item -ItemType Directory -Force -Path $DbDir | Out-Null

docker run -d `
    --name $Container `
    -p 8000:8000 `
    -v "${DbDir}:/app/db" `
    @EnvArgs `
    $Image

Write-Host "FinAlly is starting at $Url"
Start-Process $Url
