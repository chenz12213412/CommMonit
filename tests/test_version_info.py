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
