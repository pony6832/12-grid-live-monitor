$ErrorActionPreference = "Stop"

. "$PSScriptRoot\use-local-ffmpeg.ps1"

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "ffmpeg was not found in PATH."
}

if (-not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    throw "ffprobe was not found in PATH."
}

if (-not (Test-Path ".\.venv")) {
    $pythonExe = $null
    $pythonArgs = @()

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.11 -c "import sys" *> $null
        if ($LASTEXITCODE -eq 0) {
            $pythonExe = "py"
            $pythonArgs = @("-3.11")
        }
    }

    if (-not $pythonExe) {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCommand) {
            $pythonExe = $pythonCommand.Source
        }
    }

    if (-not $pythonExe) {
        $bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
        if (Test-Path $bundledPython) {
            $pythonExe = $bundledPython
        }
    }

    if (-not $pythonExe) {
        throw "Python 3.11+ was not found. Install Python 3.11+ first."
    }

    & $pythonExe @pythonArgs -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "Install complete. Start the app with .\run.ps1"
