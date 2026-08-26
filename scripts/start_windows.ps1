$ErrorActionPreference = "Stop"
# One-command start: builds the finally image if needed, runs the container
# with the db/ bind mount, and waits for it to become healthy.
# Idempotent -- safe to run repeatedly. This is the PowerShell equivalent of
# start_mac.sh; keep the two branch-for-branch in sync.

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Image = "finally"
$Name = "finally-app"
$HostPort = 8000

Write-Host "==> Checking Docker is running"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Desktop does not appear to be running."
    Write-Host "Please start Docker Desktop and try again."
    exit 1
}

docker image inspect $Image *> $null
$imageMissing = ($LASTEXITCODE -ne 0)
if ($imageMissing -or ($args -contains "--build")) {
    Write-Host "==> Building image $Image"
    docker build -t $Image $RepoRoot
    if ($LASTEXITCODE -ne 0) { exit 1 }
} else {
    Write-Host "==> Image $Image already built, skipping build (pass --build to force a rebuild)"
}

$EnvArgs = @()
$EnvFile = Join-Path $RepoRoot ".env"
if (Test-Path $EnvFile) {
    $EnvArgs += @("--env-file", $EnvFile)
} else {
    Write-Host "==> No .env file found -- AI chat will be unavailable without OPENROUTER_API_KEY (prices and trading still work)"
}

$DbDir = Join-Path $RepoRoot "db"
New-Item -ItemType Directory -Force -Path $DbDir | Out-Null

$stateRaw = docker inspect -f '{{.State.Running}}' $Name 2>$null
if ($LASTEXITCODE -ne 0) {
    $State = "absent"
} else {
    $State = ($stateRaw | Out-String).Trim()
}

switch ($State) {
    "true" {
        Write-Host "finally is already running at http://localhost:$HostPort"
        exit 0
    }
    "false" {
        Write-Host "==> Starting existing container $Name"
        docker start $Name | Out-Null
    }
    "absent" {
        Write-Host "==> Running new container $Name"
        docker run -d --name $Name -v "${RepoRoot}\db:/app/db" -p "${HostPort}:8000" --stop-timeout 15 @EnvArgs $Image | Out-Null
        if ($LASTEXITCODE -ne 0) { exit 1 }
    }
}

Write-Host "==> Waiting for /api/health"
$Ready = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$HostPort/api/health" -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            $Ready = $true
            break
        }
    } catch {
        # not ready yet, keep polling
    }
    Start-Sleep -Milliseconds 500
}
if (-not $Ready) {
    Write-Host "FAIL: server did not answer /api/health within 20s"
    docker logs --tail 20 $Name
    exit 1
}

Write-Host "Open http://localhost:$HostPort"

try {
    Start-Process "http://localhost:$HostPort" | Out-Null
} catch {
    # opening a browser is best-effort only
}
