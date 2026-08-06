# CommMonit Version Management and Gitee Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 CommMonit 建立以 `app/version.py` 为唯一来源的 `v1.0.0` 版本体系，为两种 Windows EXE 写入版本信息，并发布到 GitHub 与 Gitee 私有仓库。

**Architecture:** 运行时和构建时均从 `app/version.py` 读取版本。独立工具生成 PyInstaller Windows 版本资源，PowerShell 构建与发布脚本负责校验、测试、打包、打标签和双远程推送；发布失败时回滚本地及已推送的标签。

**Tech Stack:** Python 3.13、PySide6、PyInstaller、PowerShell、`unittest`、Git、Gitee 网页端。

---

## 文件结构

- Create: `app/version.py`，定义产品名称、中文描述、语义化版本、标签和 Windows 四段版本。
- Create: `tests/test_version.py`，验证版本格式、派生值、Qt 应用元数据和窗口标题。
- Modify: `main.py`，把版本写入 `QApplication`。
- Modify: `app/ui.py`，在窗口标题中显示版本。
- Create: `tools/make_version_info.py`，生成 PyInstaller Windows 版本资源。
- Create: `tests/test_version_info.py`，验证资源内容、UTF-8 无 BOM 和 CRLF。
- Modify: `CommMonit.spec`，为单文件 EXE 引用版本资源。
- Modify: `CommMonit-folder.spec`，为目录版 EXE 引用版本资源。
- Modify: `build.ps1`，在测试和打包前生成版本资源。
- Modify: `.gitignore`，忽略生成的 `tools/generated/`。
- Create: `CHANGELOG.md`，记录 `1.0.0` 首次正式发布内容。
- Modify: `README.md`，说明版本规则和发布命令。
- Create: `tools/release_checks.py`，校验请求版本、代码版本和更新日志一致。
- Create: `tests/test_release_checks.py`，覆盖发布元数据校验。
- Create: `release.ps1`，执行构建、双远程同步、标签发布和失败回滚。

### Task 1: 建立唯一版本源

**Files:**
- Create: `tests/test_version.py`
- Create: `app/version.py`

- [ ] **Step 1: 写入失败的版本测试**

```python
import re
import unittest

from app.version import (
    APP_VERSION,
    FILE_DESCRIPTION,
    PRODUCT_NAME,
    VERSION_TAG,
    WINDOWS_VERSION,
)


class VersionTests(unittest.TestCase):
    def test_version_values_are_consistent(self):
        self.assertRegex(APP_VERSION, r"^\d+\.\d+\.\d+$")
        self.assertEqual(APP_VERSION, "1.0.0")
        self.assertEqual(VERSION_TAG, "v1.0.0")
        self.assertEqual(WINDOWS_VERSION, (1, 0, 0, 0))

    def test_product_metadata(self):
        self.assertEqual(PRODUCT_NAME, "CommMonit")
        self.assertEqual(FILE_DESCRIPTION, "串口旁路监控软件")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认因版本模块不存在而失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_version -v
```

Expected: `ModuleNotFoundError: No module named 'app.version'`。

- [ ] **Step 3: 实现唯一版本源**

```python
"""CommMonit product and release version metadata."""

APP_VERSION = "1.0.0"
PRODUCT_NAME = "CommMonit"
FILE_DESCRIPTION = "串口旁路监控软件"

_VERSION_PARTS = tuple(int(part) for part in APP_VERSION.split("."))
if len(_VERSION_PARTS) != 3:
    raise RuntimeError(f"无效的 CommMonit 版本号：{APP_VERSION}")

WINDOWS_VERSION = (*_VERSION_PARTS, 0)
VERSION_TAG = f"v{APP_VERSION}"
```

- [ ] **Step 4: 运行版本测试并确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_version -v
```

Expected: `Ran 2 tests` 和 `OK`。

- [ ] **Step 5: 提交版本源**

```powershell
git add -- app/version.py tests/test_version.py
git commit -m "feat: add canonical application version"
```

### Task 2: 将版本写入 Qt 应用和窗口标题

**Files:**
- Modify: `tests/test_version.py`
- Modify: `main.py:9-34`
- Modify: `app/ui.py:39-45,199`

- [ ] **Step 1: 扩展失败的 Qt 元数据测试**

在 `tests/test_version.py` 顶部增加：

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui import MainWindow
from main import configure_application
```

在 `VersionTests` 中增加：

```python
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_qt_application_and_window_expose_version(self):
        configure_application(self.app, "dark")
        window = MainWindow(theme="dark")
        self.addCleanup(window.close)
        self.assertEqual(self.app.applicationVersion(), APP_VERSION)
        self.assertIn(VERSION_TAG, window.windowTitle())
        self.assertIn(FILE_DESCRIPTION, window.windowTitle())
```

- [ ] **Step 2: 运行测试并确认缺少 `configure_application`**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_version.VersionTests.test_qt_application_and_window_expose_version -v
```

Expected: 导入 `configure_application` 失败。

- [ ] **Step 3: 在 `main.py` 集中配置 Qt 应用元数据**

增加导入：

```python
from app.version import APP_VERSION
```

增加函数：

```python
def configure_application(app: QApplication, theme: str) -> None:
    app.setApplicationName("CommMonit")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("CommMonit")
    app.setStyle("Fusion")
    app.setPalette(palette_for_theme(theme))
    app.setStyleSheet(APP_STYLESHEET)
```

将 `main()` 中对应的六行 Qt 配置替换为：

```python
    configure_application(app, theme)
```

主题读取与合法值校验保留在调用前。

- [ ] **Step 4: 在 `app/ui.py` 显示版本**

增加导入：

```python
from app.version import FILE_DESCRIPTION, VERSION_TAG
```

将窗口标题设置改为：

```python
        self.setWindowTitle(f"CommMonit {VERSION_TAG} · {FILE_DESCRIPTION}")
```

- [ ] **Step 5: 运行版本和现有测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: 全部测试通过，无 `FAILED` 或 `ERROR`。

- [ ] **Step 6: 提交 Qt 版本展示**

```powershell
git add -- main.py app/ui.py tests/test_version.py
git commit -m "feat: show application version in Qt"
```

### Task 3: 生成 Windows EXE 版本资源

**Files:**
- Create: `tests/test_version_info.py`
- Create: `tools/make_version_info.py`

- [ ] **Step 1: 写入失败的版本资源测试**

```python
import tempfile
import unittest
from pathlib import Path

from tools.make_version_info import render_version_info, write_version_info


class VersionInfoTests(unittest.TestCase):
    def test_rendered_metadata_contains_product_values(self):
        content = render_version_info()
        self.assertIn("filevers=(1, 0, 0, 0)", content)
        self.assertIn("prodvers=(1, 0, 0, 0)", content)
        self.assertIn("串口旁路监控软件", content)
        self.assertIn("1.0.0.0", content)

    def test_written_resource_is_utf8_without_bom_and_crlf(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "commmonit-version.txt"
            write_version_info(output)
            data = output.read_bytes()
            self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\n", data.replace(b"\r\n", b""))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认生成器不存在**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_version_info -v
```

Expected: `ModuleNotFoundError: No module named 'tools.make_version_info'`。

- [ ] **Step 3: 实现资源生成器**

```python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.version import APP_VERSION, FILE_DESCRIPTION, PRODUCT_NAME, WINDOWS_VERSION

OUTPUT_PATH = ROOT / "tools" / "generated" / "commmonit-version.txt"


def render_version_info() -> str:
    version_tuple = ", ".join(str(part) for part in WINDOWS_VERSION)
    file_version = f"{APP_VERSION}.0"
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_tuple}),
    prodvers=({version_tuple}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '080404b0',
        [
          StringStruct('FileDescription', '{FILE_DESCRIPTION}'),
          StringStruct('FileVersion', '{file_version}'),
          StringStruct('InternalName', '{PRODUCT_NAME}'),
          StringStruct('OriginalFilename', 'CommMonit.exe'),
          StringStruct('ProductName', '{PRODUCT_NAME}'),
          StringStruct('ProductVersion', '{file_version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)"""


def write_version_info(output: Path = OUTPUT_PATH) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_version_info(), encoding="utf-8", newline="\r\n")
    return output


if __name__ == "__main__":
    print(write_version_info())
```

- [ ] **Step 4: 运行资源测试并确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_version_info -v
```

Expected: `Ran 2 tests` 和 `OK`。

- [ ] **Step 5: 提交资源生成器**

```powershell
git add -- tools/make_version_info.py tests/test_version_info.py
git commit -m "feat: generate Windows version metadata"
```

### Task 4: 将版本资源接入两种 PyInstaller 构建

**Files:**
- Create: `tests/test_build_config.py`
- Modify: `CommMonit.spec:28-50`
- Modify: `CommMonit-folder.spec:28-49`
- Modify: `build.ps1:10-15`
- Modify: `.gitignore`

- [ ] **Step 1: 写入失败的构建配置测试**

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VERSION_RESOURCE = "tools/generated/commmonit-version.txt"


class BuildConfigTests(unittest.TestCase):
    def test_both_specs_reference_generated_version_resource(self):
        for name in ("CommMonit.spec", "CommMonit-folder.spec"):
            content = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn(f'version="{VERSION_RESOURCE}"', content)

    def test_build_generates_version_resource_before_tests(self):
        content = (ROOT / "build.ps1").read_text(encoding="utf-8")
        generator = content.index("tools\\make_version_info.py")
        tests = content.index("-m unittest discover")
        self.assertLess(generator, tests)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认 spec 尚未引用版本资源**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_build_config -v
```

Expected: 两项测试至少一项失败。

- [ ] **Step 3: 修改两个 spec 文件**

在两个 `EXE(...)` 调用的 `icon` 参数后增加：

```python
    version="tools/generated/commmonit-version.txt",
```

- [ ] **Step 4: 修改构建脚本**

在图标生成命令后增加：

```powershell
& $Python (Join-Path $ProjectRoot "tools\make_version_info.py")
$VersionResource = Join-Path $ProjectRoot "tools\generated\commmonit-version.txt"
if (-not (Test-Path -LiteralPath $VersionResource)) {
    throw "未生成 Windows 版本资源：$VersionResource"
}
```

- [ ] **Step 5: 忽略生成目录**

在 `.gitignore` 末尾增加：

```gitignore
tools/generated/
```

- [ ] **Step 6: 运行全部测试和双版本构建**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\build.ps1
```

Expected: 测试全部通过，并生成 `dist\CommMonit.exe` 与 `dist\CommMonit-folder\CommMonit.exe`。

- [ ] **Step 7: 检查两个 EXE 的 Windows 元数据**

Run:

```powershell
Get-Item '.\dist\CommMonit.exe', '.\dist\CommMonit-folder\CommMonit.exe' |
    ForEach-Object { $_.VersionInfo } |
    Select-Object FileName,FileVersion,ProductVersion,ProductName,FileDescription
```

Expected: 两个文件的 `FileVersion` 和 `ProductVersion` 为 `1.0.0.0`，`ProductName` 为 `CommMonit`，`FileDescription` 为“串口旁路监控软件”。

- [ ] **Step 8: 提交构建接入**

```powershell
git add -- .gitignore build.ps1 CommMonit.spec CommMonit-folder.spec tests/test_build_config.py
git commit -m "feat: embed version metadata in Windows builds"
```

### Task 5: 添加更新日志和发布说明

**Files:**
- Modify: `tests/test_version.py`
- Create: `CHANGELOG.md`
- Modify: `README.md`

- [ ] **Step 1: 增加失败的更新日志一致性测试**

在 `tests/test_version.py` 增加 `Path` 导入和测试：

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
```

```python
    def test_changelog_contains_current_release(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## [{APP_VERSION}] - 2026-08-06", changelog)
```

- [ ] **Step 2: 运行测试并确认缺少更新日志**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_version.VersionTests.test_changelog_contains_current_release -v
```

Expected: `FileNotFoundError`。

- [ ] **Step 3: 新增 `CHANGELOG.md`**

```markdown
# 更新日志

本文件记录 CommMonit 的正式版本变化。版本号遵循语义化版本规范。

## [1.0.0] - 2026-08-06

### 新增

- 监控已被目标进程打开的 Windows 串口，不抢占串口。
- 支持同时监控多个目标进程，串口关闭后自动停止对应会话。
- 展示收发方向、进程、串口参数、HEX 和 ASCII 数据。
- 支持筛选、暂停、清空、复制以及 CSV/JSON 导出。
- 支持工业风亮色与暗色主题快速切换。
- 支持启动多个独立软件实例。
- 提供单文件版和目录版 Windows EXE。
```

- [ ] **Step 4: 在 `README.md` 追加版本说明**

```markdown
## 版本管理与发布

当前版本：`v1.0.0`。

版本号遵循 `主版本.次版本.修订版本`。正式发布前必须更新 `app/version.py` 和 `CHANGELOG.md`，再运行：

```powershell
.\release.ps1 -Version 1.0.0
```

发布脚本会验证版本、运行测试、构建两种 EXE，并将 `main` 和版本标签同步到 GitHub 与 Gitee。
```

- [ ] **Step 5: 运行全部测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: 全部测试通过。

- [ ] **Step 6: 提交更新日志和文档**

```powershell
git add -- CHANGELOG.md README.md tests/test_version.py
git commit -m "docs: add v1.0.0 release notes"
```

### Task 6: 添加发布校验和双远程发布脚本

**Files:**
- Create: `tests/test_release_checks.py`
- Create: `tools/release_checks.py`
- Create: `release.ps1`

- [ ] **Step 1: 写入失败的发布校验测试**

```python
import unittest

from tools.release_checks import validate_release_metadata


class ReleaseChecksTests(unittest.TestCase):
    def test_accepts_matching_version_and_changelog(self):
        validate_release_metadata("1.0.0", "## [1.0.0] - 2026-08-06")

    def test_rejects_invalid_semantic_version(self):
        with self.assertRaisesRegex(ValueError, "语义化版本"):
            validate_release_metadata("1.0", "## [1.0] - 2026-08-06")

    def test_rejects_version_different_from_application(self):
        with self.assertRaisesRegex(ValueError, "应用版本"):
            validate_release_metadata("1.0.1", "## [1.0.1] - 2026-08-06")

    def test_rejects_missing_changelog_entry(self):
        with self.assertRaisesRegex(ValueError, "更新日志"):
            validate_release_metadata("1.0.0", "# 更新日志")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认校验模块不存在**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_release_checks -v
```

Expected: `ModuleNotFoundError: No module named 'tools.release_checks'`。

- [ ] **Step 3: 实现发布元数据校验**

```python
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.version import APP_VERSION

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def validate_release_metadata(requested_version: str, changelog: str) -> None:
    if not SEMVER_PATTERN.fullmatch(requested_version):
        raise ValueError(f"发布版本不符合语义化版本格式：{requested_version}")
    if requested_version != APP_VERSION:
        raise ValueError(
            f"请求版本 {requested_version} 与应用版本 {APP_VERSION} 不一致"
        )
    if f"## [{requested_version}]" not in changelog:
        raise ValueError(f"更新日志缺少版本 {requested_version} 的条目")


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 CommMonit 发布元数据")
    parser.add_argument("version")
    args = parser.parse_args()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    validate_release_metadata(args.version, changelog)
    print(f"发布元数据校验通过：v{args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行校验测试并确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_release_checks -v
```

Expected: `Ran 4 tests` 和 `OK`。

- [ ] **Step 5: 实现 `release.ps1`**

```powershell
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
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
```

- [ ] **Step 6: 仅执行无副作用的发布前校验**

Run:

```powershell
.\.venv\Scripts\python.exe .\tools\release_checks.py 1.0.0
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: 显示“发布元数据校验通过：v1.0.0”，全部测试通过。此时不运行 `release.ps1`，因为 Gitee 远程尚未创建。

- [ ] **Step 7: 提交发布脚本**

```powershell
git add -- release.ps1 tools/release_checks.py tests/test_release_checks.py
git commit -m "feat: add validated dual-remote release flow"
```

### Task 7: 完整本地验收

**Files:**
- Verify only

- [ ] **Step 1: 运行全部测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: 所有测试通过，失败数和错误数均为零。

- [ ] **Step 2: 重新构建两种 EXE**

Run:

```powershell
.\build.ps1
```

Expected: 命令退出码为零，并输出两个 EXE 的绝对路径。

- [ ] **Step 3: 校验 EXE 元数据和程序截图**

Run:

```powershell
Get-Item '.\dist\CommMonit.exe', '.\dist\CommMonit-folder\CommMonit.exe' |
    ForEach-Object { $_.VersionInfo } |
    Select-Object FileName,FileVersion,ProductVersion,ProductName,FileDescription

.\.venv\Scripts\python.exe .\main.py --screenshot .\artifacts\version-v1.0.0.png
```

Expected: 两个 EXE 元数据一致，截图标题包含 `v1.0.0`，界面布局没有变化。

- [ ] **Step 4: 执行文本编码和行尾扫描**

Run:

```powershell
$textFiles = Get-ChildItem -Path . -Recurse -File | Where-Object {
    $_.FullName -notmatch '\\(\.git|\.venv|build|dist|artifacts|__pycache__|generated)\\' -and
    $_.Extension -in '.py','.md','.ps1','.spec','.js','.txt','.json','.svg','.gitignore'
}
$mojibakePattern = '\u951F\u65A4\u62F7|\u70EB\u70EB\u70EB|\u5C6F\u5C6F\u5C6F|\u9225|\u9983|\u00C3.|\u00C2.|\u00E2\u20AC|\u00EF\u00BB\u00BF|\uFFFD'
foreach ($File in $textFiles) {
    $Bytes = [System.IO.File]::ReadAllBytes($File.FullName)
    $Text = [System.Text.Encoding]::UTF8.GetString($Bytes)
    if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF) {
        throw "文件包含 UTF-8 BOM：$($File.FullName)"
    }
    if ($Text -match '(?<!\r)\n') {
        throw "文件不是 CRLF 行尾：$($File.FullName)"
    }
    if ($Text -match $mojibakePattern) {
        throw "文件包含乱码特征：$($File.FullName)"
    }
}
```

Expected: 无异常输出。

- [ ] **Step 5: 检查提交边界**

Run:

```powershell
git status -sb
git log -8 --oneline
```

Expected: 工作区干净，版本管理改造由多个聚焦提交组成。

### Task 8: 创建 Gitee 私有仓库并发布 `v1.0.0`

**Files:**
- External repository configuration only

- [ ] **Step 1: 在已登录的 Gitee 页面创建仓库**

使用账号 `yycz（陈臻）` 打开 `https://gitee.com/projects/new`，设置：

```text
仓库名称/显示名称：串口旁路监控软件
仓库路径：commmonit
可见性：私有
初始化 README：关闭
初始化 .gitignore：关闭
初始化许可证：关闭
默认分支：main
```

提交后确认仓库地址为 `https://gitee.com/yycz/commmonit`，且页面显示中文名称“串口旁路监控软件”。

- [ ] **Step 2: 配置第二远程并验证**

Run:

```powershell
git remote add gitee https://gitee.com/yycz/commmonit.git
git remote -v
```

Expected: `origin` 指向 GitHub，`gitee` 指向 `https://gitee.com/yycz/commmonit.git`。

- [ ] **Step 3: 运行正式发布脚本**

Run:

```powershell
.\release.ps1 -Version 1.0.0
```

Expected: 测试和双构建通过，`main` 同步到两个远程，创建并推送 `v1.0.0`，最后显示“发布完成：v1.0.0”。

- [ ] **Step 4: 核对本地与双远程提交和标签**

Run:

```powershell
$LocalHead = git rev-parse HEAD
$GitHubHead = (git ls-remote origin refs/heads/main).Split()[0]
$GiteeHead = (git ls-remote gitee refs/heads/main).Split()[0]
$GitHubTag = git ls-remote origin refs/tags/v1.0.0
$GiteeTag = git ls-remote gitee refs/tags/v1.0.0

Write-Output "LOCAL=$LocalHead"
Write-Output "GITHUB=$GitHubHead"
Write-Output "GITEE=$GiteeHead"
Write-Output "GITHUB_TAG=$GitHubTag"
Write-Output "GITEE_TAG=$GiteeTag"

if ($LocalHead -ne $GitHubHead -or $LocalHead -ne $GiteeHead) {
    throw "本地、GitHub 与 Gitee 的 main 提交不一致。"
}
if (-not $GitHubTag -or -not $GiteeTag) {
    throw "至少一个远程缺少 v1.0.0 标签。"
}
```

Expected: 三个 `main` 哈希一致，两个远程均返回 `v1.0.0` 标签。

- [ ] **Step 5: 最终检查**

Run:

```powershell
git status -sb
git tag --list --sort=-version:refname
```

Expected: 工作区干净，当前分支为 `main`，标签列表包含 `v1.0.0`。
