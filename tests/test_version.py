import importlib
import unittest
from unittest.mock import patch

import app
import app.version as version_metadata
from app.version import APP_VERSION, FILE_DESCRIPTION, PRODUCT_NAME, VERSION_TAG, WINDOWS_VERSION


class VersionMetadataTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
