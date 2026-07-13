$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Running install.ps1 first."
    .\install.ps1
}

$packageRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
$mpvInstalled = (Get-Command mpv -ErrorAction SilentlyContinue) -or (Get-ChildItem $packageRoot -Filter mpv.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1)
$ytdlpInstalled = (Get-Command yt-dlp -ErrorAction SilentlyContinue) -or (Get-ChildItem $packageRoot -Filter yt-dlp.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $mpvInstalled -or -not $ytdlpInstalled) {
    .\install-light-player.ps1
}

.\.venv\Scripts\python.exe -m app.light_player
