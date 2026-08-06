"""CommMonit product and release version metadata."""
APP_VERSION = "1.0.0"
PRODUCT_NAME = "CommMonit"
FILE_DESCRIPTION = "串口旁路监控软件"
_VERSION_PARTS = tuple(int(part) for part in APP_VERSION.split("."))
if len(_VERSION_PARTS) != 3:
    raise RuntimeError(f"无效的 CommMonit 版本号：{APP_VERSION}")
WINDOWS_VERSION = (*_VERSION_PARTS, 0)
VERSION_TAG = f"v{APP_VERSION}"
