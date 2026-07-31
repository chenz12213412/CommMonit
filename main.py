from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication

from app.styles import APP_STYLESHEET, palette_for_theme
from app.ui import MainWindow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CommMonit Windows 串口旁路监控")
    parser.add_argument("--demo", action="store_true", help="使用演示数据启动")
    parser.add_argument("--screenshot", metavar="PATH", help="保存界面截图并退出")
    parser.add_argument("--new-instance", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("CommMonit")
    app.setOrganizationName("CommMonit")
    app.setStyle("Fusion")
    theme = str(QSettings("CommMonit", "CommMonit").value("theme", "dark"))
    if theme not in ("dark", "light"):
        theme = "dark"
    app.setPalette(palette_for_theme(theme))
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow(demo=args.demo or bool(args.screenshot), theme=theme)
    window.show()
    if args.screenshot:
        output = Path(args.screenshot).resolve()

        def save_screenshot() -> None:
            output.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(output))
            app.quit()

        QTimer.singleShot(1200, save_screenshot)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
