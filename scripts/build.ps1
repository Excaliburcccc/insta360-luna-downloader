$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    py -3 -m venv (Join-Path $repoRoot ".venv")
}

& $python -m pip install --upgrade pip
& $python -m pip install -e "${repoRoot}[dev]"
& $python -m pytest

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "Insta360LunaDownloader" `
    --paths (Join-Path $repoRoot "src") `
    (Join-Path $repoRoot "src\luna_downloader\main.py")

Write-Host "Built: $(Join-Path $repoRoot 'dist\Insta360LunaDownloader\Insta360LunaDownloader.exe')"
