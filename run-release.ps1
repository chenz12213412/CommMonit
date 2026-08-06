[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ReleasePath = Join-Path $ProjectRoot "release.ps1"
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$ReleaseText = [System.IO.File]::ReadAllText($ReleasePath, $Utf8)

& ([scriptblock]::Create($ReleaseText)) -Version $Version
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
