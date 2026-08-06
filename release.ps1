[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$ScriptPath = $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ScriptPath)) {
    $ProjectRoot = (Get-Location).Path
} else {
    $ProjectRoot = Split-Path -Parent $ScriptPath
}
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Tag = "v$Version"
$Remotes = @("origin", "gitee")

function Invoke-Git {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Git 命令失败：git $($Arguments -join ' ')"
    }
}

Push-Location $ProjectRoot
try {
    $Branch = (& git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or $Branch -ne "main") {
        throw "正式发布必须在 main 分支执行，当前分支：$Branch"
    }

    $Dirty = & git status --porcelain
    if ($LASTEXITCODE -ne 0 -or $Dirty) {
        throw "工作区存在未提交修改，不能发布。"
    }

    $ConfiguredRemotes = @(& git remote)
    foreach ($Remote in $Remotes) {
        if ($ConfiguredRemotes -notcontains $Remote) {
            throw "缺少 Git 远程：$Remote"
        }
    }

    & $Python (Join-Path $ProjectRoot "tools\release_checks.py") $Version
    if ($LASTEXITCODE -ne 0) {
        throw "发布元数据校验失败。"
    }

    & git rev-parse --verify --quiet "refs/tags/$Tag" *> $null
    if ($LASTEXITCODE -eq 0) {
        throw "标签已存在：$Tag"
    }

    & (Join-Path $ProjectRoot "build.ps1")

    foreach ($Remote in $Remotes) {
        Invoke-Git -Arguments @("push", $Remote, "main")
    }

    Invoke-Git -Arguments @("tag", "-a", $Tag, "-m", "CommMonit $Tag")
    $PushedTagRemotes = [System.Collections.Generic.List[string]]::new()
    try {
        foreach ($Remote in $Remotes) {
            Invoke-Git -Arguments @("push", $Remote, $Tag)
            $PushedTagRemotes.Add($Remote)
        }
    }
    catch {
        foreach ($Remote in $PushedTagRemotes) {
            & git push $Remote ":refs/tags/$Tag"
        }
        & git tag -d $Tag
        throw
    }

    Write-Host "发布完成：$Tag"
}
finally {
    Pop-Location
}
