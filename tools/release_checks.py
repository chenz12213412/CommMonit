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
