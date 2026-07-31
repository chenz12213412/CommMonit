from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication, QIcon


app = QGuiApplication([])
root = Path(__file__).resolve().parent.parent
icon = QIcon(str(root / "assets" / "logo.svg"))
pixmap = icon.pixmap(QSize(256, 256))
if not pixmap.save(str(root / "assets" / "commmonit.ico"), "ICO"):
    raise SystemExit("Qt ICO image plugin is unavailable")

