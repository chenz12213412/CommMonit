$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    & "C:\Program Files\Python313\python.exe" -m venv (Join-Path $ProjectRoot ".venv")
}

& $Python -m pip install --disable-pip-version-check -r (Join-Path $ProjectRoot "requirements.txt")
& $Python (Join-Path $ProjectRoot "tools\make_icon.py")
& $Python -m unittest discover -s (Join-Path $ProjectRoot "tests") -v
& $Python -m PyInstaller --noconfirm --clean (Join-Path $ProjectRoot "CommMonit.spec")

$Output = Join-Path $ProjectRoot "dist\CommMonit.exe"
if (-not (Test-Path -LiteralPath $Output)) {
    throw "Build finished without creating $Output"
}

Write-Host "Built: $Output"
