$ErrorActionPreference = "Stop"

Write-Host "Installing mpv..."
winget install --id mpv-player.mpv-CI.MSVC --exact --accept-package-agreements --accept-source-agreements

Write-Host "Installing yt-dlp..."
winget install --id yt-dlp.yt-dlp --exact --accept-package-agreements --accept-source-agreements

$wingetLinks = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"
if (Test-Path $wingetLinks) {
    $env:PATH = "$wingetLinks;$env:PATH"
}

Write-Host "Light player dependencies are ready."
