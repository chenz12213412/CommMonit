$ErrorActionPreference = "Stop"

$ScriptPath = $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ScriptPath)) {
    $ProjectRoot = (Get-Location).Path
} else {
    $ProjectRoot = Split-Path -Parent $ScriptPath
}
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $Output = & $FilePath @Arguments 2>&1
    $ErrorActionPreference = $PreviousErrorActionPreference
    $Output | Write-Host
    if ($LASTEXITCODE -ne 0) {
        throw "命令执行失败：$FilePath $($Arguments -join ' ')"
    }
}

if (-not (Test-Path -LiteralPath $Python)) {
    Invoke-CheckedCommand -FilePath "C:\Program Files\Python313\python.exe" -Arguments @(
        "-m", "venv", (Join-Path $ProjectRoot ".venv")
    )
}

Invoke-CheckedCommand -FilePath $Python -Arguments @(
    "-m", "pip", "install", "--disable-pip-version-check", "-r",
    (Join-Path $ProjectRoot "requirements.txt")
)
Invoke-CheckedCommand -FilePath $Python -Arguments @((Join-Path $ProjectRoot "tools\make_icon.py"))
Invoke-CheckedCommand -FilePath $Python -Arguments @((Join-Path $ProjectRoot "tools\make_version_info.py"))
$VersionResource = Join-Path $ProjectRoot "tools\generated\commmonit-version.txt"
if (-not (Test-Path -LiteralPath $VersionResource)) {
    throw "未生成 Windows 版本资源：$VersionResource"
}
Invoke-CheckedCommand -FilePath $Python -Arguments @(
    "-m", "unittest", "discover", "-s", (Join-Path $ProjectRoot "tests"), "-q"
)
Invoke-CheckedCommand -FilePath $Python -Arguments @(
    "-m", "PyInstaller", "--noconfirm", "--clean", (Join-Path $ProjectRoot "CommMonit.spec")
)
Invoke-CheckedCommand -FilePath $Python -Arguments @(
    "-m", "PyInstaller", "--noconfirm", "--clean", (Join-Path $ProjectRoot "CommMonit-folder.spec")
)

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
