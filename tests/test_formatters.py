import csv
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.formatters import CaptureEvent, export_csv, export_json, format_ascii, format_hex, format_size


class FormatterTests(unittest.TestCase):
    def test_hex_and_ascii(self):
        data = b"ABC\x00\xff"
        self.assertEqual(format_hex(data), "41 42 43 00 FF")
        self.assertEqual(format_ascii(data), "ABC··")

    def test_limits(self):
        self.assertEqual(format_hex(bytes(range(4)), 2), "00 01 …")
        self.assertEqual(format_ascii(b"abcd", 2), "ab…")

    def test_size(self):
        self.assertEqual(format_size(100), "100 B")
        self.assertEqual(format_size(2048), "2.0 KB")

    def test_exports(self):
        event = CaptureEvent(
            datetime(2026, 7, 31, 12, 0),
            "rx",
            "COM3",
            b"A\x00",
            115200,
            "8N1",
            4248,
        )
        with tempfile.TemporaryDirectory() as folder:
            csv_path = Path(folder) / "capture.csv"
            json_path = Path(folder) / "capture.json"
            export_csv(csv_path, [event])
            export_json(json_path, [event])
            with csv_path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            with json_path.open(encoding="utf-8") as stream:
                records = json.load(stream)
            self.assertEqual(rows[0]["hex"], "41 00")
            self.assertEqual(rows[0]["process_id"], "4248")
            self.assertEqual(records[0]["direction"], "RX")


if __name__ == "__main__":
    unittest.main()
