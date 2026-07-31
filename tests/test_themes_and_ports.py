import unittest

from PySide6.QtGui import QPalette

from app.styles import APP_STYLESHEET, palette_for_theme


class ThemeAndPortTests(unittest.TestCase):
    def test_light_and_dark_palettes_are_distinct(self):
        dark = palette_for_theme("dark")
        light = palette_for_theme("light")
        self.assertNotEqual(dark.color(QPalette.Window), light.color(QPalette.Window))
        self.assertNotEqual(dark.color(QPalette.Highlight), light.color(QPalette.Highlight))
        self.assertIn('QPushButton[primary="true"]', APP_STYLESHEET)


if __name__ == "__main__":
    unittest.main()
