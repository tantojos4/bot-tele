param(
    [switch]$NoCompose
)
# Copy .env.dev -> .env (be sure to not commit .env)
Set-Content -Path .env -Value (Get-Content .env.dev -Raw)

if (-not $NoCompose) {
    .\scripts\start_postgres_dev.ps1
}

# run the bot in current shell
Write-Host "Running bot.py using $(Get-Command python)."
python .\bot.py
