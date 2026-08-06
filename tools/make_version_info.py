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
