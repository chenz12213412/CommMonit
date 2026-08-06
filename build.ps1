$ErrorActionPreference = "Stop"

$ScriptPath = $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ScriptPath)) {
    $ProjectRoot = (Get-Location).Path
} else {
    $ProjectRoot = Split-Path -Parent $ScriptPath
}
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    & "C:\Program Files\Python313\python.exe" -m venv (Join-Path $ProjectRoot ".venv") 2>&1 | Out-Host
}

& $Python -m pip install --disable-pip-version-check -r (Join-Path $ProjectRoot "requirements.txt") 2>&1 | Out-Host
& $Python (Join-Path $ProjectRoot "tools\make_icon.py") 2>&1 | Out-Host
& $Python (Join-Path $ProjectRoot "tools\make_version_info.py") 2>&1 | Out-Host
$VersionResource = Join-Path $ProjectRoot "tools\generated\commmonit-version.txt"
if (-not (Test-Path -LiteralPath $VersionResource)) {
    throw "未生成 Windows 版本资源：$VersionResource"
}
& $Python -m unittest discover -s (Join-Path $ProjectRoot "tests") -q 2>&1 | Out-Host
& $Python -m PyInstaller --noconfirm --clean (Join-Path $ProjectRoot "CommMonit.spec") 2>&1 | Out-Host
& $Python -m PyInstaller --noconfirm --clean (Join-Path $ProjectRoot "CommMonit-folder.spec") 2>&1 | Out-Host

$SingleFileOutput = Join-Path $ProjectRoot "dist\CommMonit.exe"
$FolderOutput = Join-Path $ProjectRoot "dist\CommMonit-folder\CommMonit.exe"
if (-not (Test-Path -LiteralPath $SingleFileOutput)) {
    throw "Build finished without creating $SingleFileOutput"
}
if (-not (Test-Path -LiteralPath $FolderOutput)) {
    throw "Build finished without creating $FolderOutput"
}

Write-Host "Single-file build: $SingleFileOutput"
Write-Host "Folder build:      $FolderOutput"
