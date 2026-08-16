# Stop and remove the FinAlly container. The db/ directory is left untouched.
$ErrorActionPreference = "Stop"

$Container = "finally"

if (docker ps -aq -f "name=^$Container$") {
    docker rm -f $Container | Out-Null
    Write-Host "Stopped and removed $Container (data in db/ kept)."
} else {
    Write-Host "$Container is not running."
}
