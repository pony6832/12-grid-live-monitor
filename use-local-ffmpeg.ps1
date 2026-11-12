$localFfmpegRoot = Join-Path $PSScriptRoot "tools\ffmpeg"

if (Test-Path $localFfmpegRoot) {
    $localFfmpeg = Get-ChildItem -Path $localFfmpegRoot -Filter ffmpeg.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($localFfmpeg) {
        $localFfmpegBin = $localFfmpeg.Directory.FullName
        $pathParts = $env:PATH -split ';'
        if ($pathParts -notcontains $localFfmpegBin) {
            $env:PATH = "$localFfmpegBin;$env:PATH"
        }
    }
}
