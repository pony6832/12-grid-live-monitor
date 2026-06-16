$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Running install.ps1 first."
    .\install.ps1
}

$logDir = Join-Path $PSScriptRoot "data"
$logPath = Join-Path $logDir "youtube_watchdog.log"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-WatchdogLog {
    param([string]$Message)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logPath -Value "[$stamp] $Message" -Encoding UTF8
}

Write-WatchdogLog "YouTube Chrome grid watchdog started."

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$process = Start-Process -FilePath $python -ArgumentList "-m", "app.chrome_embed" -WorkingDirectory $PSScriptRoot -PassThru
Write-WatchdogLog "Started YouTube Chrome grid launcher process id $($process.Id)."
Wait-Process -Id $process.Id
Write-WatchdogLog "Launcher exited with code $($process.ExitCode). Chrome windows are now managed by Chrome itself."
