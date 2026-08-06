import unittest

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


if __name__ == "__main__":
    unittest.main()
