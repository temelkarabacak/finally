$ErrorActionPreference = "Stop"
# One-command stop: bounded docker stop only. Never removes the container or
# the db/ bind mount -- stopping must never destroy the user's portfolio data.
# Idempotent -- safe to run repeatedly, always exits 0. PowerShell equivalent
# of stop_mac.sh; keep the two branch-for-branch in sync.

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Name = "finally-app"

Write-Host "==> Checking Docker is running"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Desktop does not appear to be running."
    Write-Host "Please start Docker Desktop and try again."
    exit 1
}

$stateRaw = docker inspect -f '{{.State.Running}}' $Name 2>$null
if ($LASTEXITCODE -ne 0) {
    $State = "absent"
} else {
    $State = ($stateRaw | Out-String).Trim()
}

if ($State -eq "true") {
    Write-Host "==> Stopping $Name (timeout 15s)"
    docker stop --timeout 15 $Name | Out-Null
    Write-Host "finally has been stopped. Your data in $RepoRoot\db is preserved."
} else {
    Write-Host "finally is not running."
}

exit 0
