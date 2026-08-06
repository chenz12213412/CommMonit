import importlib
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import app
import app.version as version_metadata
from PySide6.QtWidgets import QApplication

from app.ui import MainWindow
from app.version import APP_VERSION, FILE_DESCRIPTION, PRODUCT_NAME, VERSION_TAG, WINDOWS_VERSION
from main import configure_application


class VersionMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_application_version_metadata(self):
        self.assertRegex(APP_VERSION, r"^\d+\.\d+\.\d+$")
        self.assertEqual(APP_VERSION, "1.0.0")
        self.assertEqual(VERSION_TAG, "v1.0.0")
        self.assertEqual(WINDOWS_VERSION, (1, 0, 0, 0))

    def test_product_metadata(self):
        self.assertEqual(PRODUCT_NAME, "CommMonit")
        self.assertEqual(FILE_DESCRIPTION, "串口旁路监控软件")

    def test_package_version_uses_canonical_application_version(self):
        self.assertEqual(app.__version__, APP_VERSION)
        try:
            with patch.object(version_metadata, "APP_VERSION", "9.8.7"):
                importlib.reload(app)
                self.assertEqual(app.__version__, version_metadata.APP_VERSION)
        finally:
            importlib.reload(app)

    def test_qt_application_and_window_expose_version(self):
        configure_application(self.qt_app, "dark")
        window = MainWindow(theme="dark")
        self.addCleanup(window.close)
        self.assertEqual(self.qt_app.applicationVersion(), APP_VERSION)
        self.assertIn(VERSION_TAG, window.windowTitle())
        self.assertIn(FILE_DESCRIPTION, window.windowTitle())


if __name__ == "__main__":
    unittest.main()
