from __future__ import annotations

from PySide6.QtGui import QColor, QPalette


APP_STYLESHEET = """
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 13px;
}

QLabel#Brand {
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 1px;
}

QLabel#SectionTitle {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1px;
}

QLabel#MetricValue {
    font-family: "Cascadia Mono", "Consolas";
    font-size: 22px;
    font-weight: 700;
}

QLabel#MetricLabel {
    font-size: 11px;
    font-weight: 600;
}

QFrame#Header, QFrame#MetricCard, QFrame#Panel {
    border: 1px solid rgba(127, 143, 158, 90);
    border-radius: 5px;
}

QPushButton:focus {
    border: 1px solid #D67A10;
}

QPushButton {
    min-height: 34px;
    padding: 0 14px;
    border: 1px solid rgba(127, 143, 158, 110);
    border-radius: 4px;
    font-weight: 600;
}

QPushButton[primary="true"] {
    color: #17100A;
    background: #E39421;
    border-color: #F2A43B;
}

QPushButton[primary="true"]:hover {
    background: #F0A133;
}

QPushButton[danger="true"] {
    color: #FFDAD7;
    background: #562623;
    border-color: #9B433C;
}

QToolButton {
    min-width: 34px;
    min-height: 34px;
    padding: 0 9px;
    border: 1px solid rgba(127, 143, 158, 110);
    border-radius: 4px;
}

QTableView, QListWidget, QPlainTextEdit {
    border: 1px solid rgba(127, 143, 158, 90);
    border-radius: 3px;
    outline: 0;
}

QTableView::item, QListWidget::item {
    padding: 6px;
}

QPlainTextEdit {
    font-family: "Cascadia Mono", "Consolas";
    font-size: 12px;
}

QTabWidget::pane {
    border: 1px solid rgba(127, 143, 158, 90);
    top: -1px;
}

QTabBar::tab {
    min-width: 78px;
    min-height: 32px;
    padding: 0 10px;
    border: 1px solid rgba(127, 143, 158, 90);
}

QTabBar::tab:selected {
    border-bottom: 2px solid #D67A10;
}

QScrollBar:vertical {
    width: 10px;
}

QScrollBar::handle:vertical {
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QToolTip {
    border: 1px solid rgba(127, 143, 158, 120);
    padding: 5px;
}
"""


def palette_for_theme(theme: str) -> QPalette:
    palette = QPalette()
    if theme == "light":
        colors = {
            QPalette.Window: "#F3F5F7",
            QPalette.WindowText: "#17212B",
            QPalette.Base: "#FFFFFF",
            QPalette.AlternateBase: "#F1F4F6",
            QPalette.ToolTipBase: "#FFFFFF",
            QPalette.ToolTipText: "#17212B",
            QPalette.Text: "#17212B",
            QPalette.Button: "#E7ECF0",
            QPalette.ButtonText: "#17212B",
            QPalette.BrightText: "#8D211A",
            QPalette.Light: "#DDE5EB",
            QPalette.Midlight: "#D4DCE3",
            QPalette.Dark: "#C5CFD8",
            QPalette.Mid: "#AAB7C4",
            QPalette.Shadow: "#7C8B99",
            QPalette.Highlight: "#CFE4F5",
            QPalette.HighlightedText: "#10283B",
            QPalette.PlaceholderText: "#5D6A78",
            QPalette.Link: "#A95B00",
        }
    else:
        colors = {
            QPalette.Window: "#0B0F14",
            QPalette.WindowText: "#E7EDF5",
            QPalette.Base: "#0A1016",
            QPalette.AlternateBase: "#111820",
            QPalette.ToolTipBase: "#1D2731",
            QPalette.ToolTipText: "#F2F5F8",
            QPalette.Text: "#E7EDF5",
            QPalette.Button: "#1A242F",
            QPalette.ButtonText: "#E7EDF5",
            QPalette.BrightText: "#FFFFFF",
            QPalette.Light: "#24313E",
            QPalette.Midlight: "#202B36",
            QPalette.Dark: "#121A22",
            QPalette.Mid: "#334252",
            QPalette.Shadow: "#070B0F",
            QPalette.Highlight: "#384F63",
            QPalette.HighlightedText: "#FFFFFF",
            QPalette.PlaceholderText: "#8D9AAA",
            QPalette.Link: "#E39421",
        }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    return palette


def stylesheet_for_theme(_theme: str) -> str:
    return APP_STYLESHEET
