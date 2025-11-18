param([string]$ComposeFile = "docker-compose.yml")
$composeFilePath = Join-Path (Get-Location) $ComposeFile
Write-Host "Stopping docker compose services defined in $composeFilePath"
try {
    docker compose -f $composeFilePath down
}
catch {
    docker-compose -f $composeFilePath down
}
Write-Host "Stopped compose services"
