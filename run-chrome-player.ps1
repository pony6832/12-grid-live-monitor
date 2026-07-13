$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    .\install.ps1
}

.\.venv\Scripts\python.exe -m app.chrome_embed
