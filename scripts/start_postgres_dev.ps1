# Start a local Postgres dev service and initialize DB schema
param(
    [string]$ComposeFile = "docker-compose.yml",
    [switch]$SkipInit
)
$composeFilePath = Join-Path (Get-Location) $ComposeFile
Write-Host "Starting local Postgres using compose file: $composeFilePath"
# Use 'docker compose' (newer) or fallback to 'docker-compose'
$dcCmd = 'docker compose'
try {
    & $dcCmd -f $composeFilePath up -d
}
catch {
    # fallback
    $dcCmd = 'docker-compose'
    & $dcCmd -f $composeFilePath up -d
}

Write-Host "Waiting for Postgres to become available (127.0.0.1:5432)..."
$max = 30
for ($i = 0; $i -lt $max; $i++) {
    $r = Test-NetConnection -ComputerName '127.0.0.1' -Port 5432 -InformationLevel Quiet
    if ($r) { Write-Host 'Postgres reachable'; break }
    Start-Sleep -Seconds 1
}

if (-not $SkipInit) {
    Write-Host 'Initializing DB schema (db.init_db())...'
    # set DATABASE_URL for the command in the current shell
    $env:DATABASE_URL = 'postgresql+asyncpg://botuser:botpass@127.0.0.1:5432/bottele'
    # Run python to initialize DB in one line to ensure PowerShell compatibility
    python -c "import asyncio, db; asyncio.run(db.init_db()); print('DB init finished')"
}

Write-Host 'Local Postgres started. To stop, use: docker compose down'