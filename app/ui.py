from __future__ import annotations

import os
import random
import sys
from collections import deque
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QProcess,
    QSettings,
    QSortFilterProxyModel,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QFont, QIcon, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .capture import CaptureController, resource_path
from .formatters import CaptureEvent, export_csv, export_json, format_ascii, format_hex, format_size
from .processes import ProcessInfo, list_processes, list_serial_ports, system_summary
from .styles import palette_for_theme


class EventTableModel(QAbstractTableModel):
    COLUMNS = ("时间", "方向", "串口", "进程", "参数", "长度", "HEX", "ASCII")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.events: list[CaptureEvent] = []
        self.max_events = 100_000
        self.theme = "dark"

    def set_theme(self, theme: str) -> None:
        self.theme = theme
        if self.events:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self.events) - 1, len(self.COLUMNS) - 1),
                [Qt.ForegroundRole],
            )

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.events)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.events):
            return None
        event = self.events[index.row()]
        column = index.column()
        if role == Qt.DisplayRole:
            values = (
                event.timestamp.strftime("%H:%M:%S.%f")[:-3],
                "RX" if event.direction == "rx" else "TX",
                event.endpoint,
                str(event.process_id or "—"),
                f"{event.baud_rate or '—'} · {event.frame or '—'}",
                str(len(event.data)),
                format_hex(event.data, 48),
                format_ascii(event.data, 48),
            )
            return values[column]
        if role == Qt.UserRole:
            return event
        if role == Qt.ForegroundRole and column == 1:
            if self.theme == "light":
                return QColor("#147A4B" if event.direction == "rx" else "#A65C00")
            return QColor("#52C58B" if event.direction == "rx" else "#E6A148")
        if role == Qt.FontRole and column in (0, 1, 3, 5, 6, 7):
            font = QFont("Cascadia Mono")
            font.setStyleHint(QFont.Monospace)
            return font
        if role == Qt.TextAlignmentRole and column in (1, 3, 5):
            return Qt.AlignCenter
        if role == Qt.ToolTipRole:
            return f"{event.direction_label} · {len(event.data)} 字节 · {event.endpoint}"
        return None

    def append_event(self, event: CaptureEvent) -> None:
        if len(self.events) >= self.max_events:
            remove_count = min(1000, len(self.events))
            self.beginRemoveRows(QModelIndex(), 0, remove_count - 1)
            del self.events[:remove_count]
            self.endRemoveRows()
        row = len(self.events)
        self.beginInsertRows(QModelIndex(), row, row)
        self.events.append(event)
        self.endInsertRows()

    def append_events(self, events: list[CaptureEvent]) -> None:
        for event in events:
            self.append_event(event)

    def clear(self) -> None:
        if not self.events:
            return
        self.beginResetModel()
        self.events.clear()
        self.endResetModel()


class EventFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.direction = "all"
        self.query = ""
        self.setDynamicSortFilter(True)

    def set_direction(self, direction: str) -> None:
        self.direction = direction
        self.invalidateFilter()

    def set_query(self, query: str) -> None:
        self.query = query.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if not isinstance(model, EventTableModel):
            return True
        event = model.events[source_row]
        if self.direction != "all" and event.direction != self.direction:
            return False
        return not self.query or self.query in event.searchable_text()


class MetricCard(QFrame):
    def __init__(self, label: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setMinimumHeight(72)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(2)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        title = QLabel(label)
        title.setObjectName("MetricLabel")
        layout.addWidget(self.value_label)
        layout.addWidget(title)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class MainWindow(QMainWindow):
    def __init__(self, demo: bool = False, theme: str = "dark") -> None:
        super().__init__()
        self.demo = demo
        self.theme = theme if theme in ("dark", "light") else "dark"
        self.controller = CaptureController(self)
        self.event_model = EventTableModel(self)
        self.event_model.set_theme(self.theme)
        self.proxy_model = EventFilterProxy(self)
        self.proxy_model.setSourceModel(self.event_model)
        self._processes: list[ProcessInfo] = []
        self._paused = False
        self._paused_events: list[CaptureEvent] = []
        self._event_times: deque[float] = deque()
        self._rx_bytes = 0
        self._tx_bytes = 0
        self._target_name = ""

        self.setWindowTitle("CommMonit · 串口旁路监控")
        self.setMinimumSize(1120, 720)
        self.resize(1420, 880)
        self.setWindowIcon(QIcon(str(resource_path("assets/logo.svg"))))

        self._build_ui()
        self._apply_palette_roles()
        self._wire_events()
        self._setup_shortcuts()
        QTimer.singleShot(50, self.refresh_inventory)

        self.metric_timer = QTimer(self)
        self.metric_timer.timeout.connect(self._update_metrics)
        self.metric_timer.start(500)

        if self.demo:
            self._start_demo()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_header())

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 14, 16, 12)
        content_layout.setSpacing(12)
        content_layout.addLayout(self._build_metrics())

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.addWidget(self._build_sidebar())
        main_splitter.addWidget(self._build_capture_panel())
        main_splitter.setSizes([320, 1080])
        content_layout.addWidget(main_splitter, 1)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        status = QStatusBar()
        self.setStatusBar(status)
        self.status_message = QLabel("就绪 · 选择占用串口的目标进程")
        self.status_system = QLabel(system_summary())
        self.status_system.setProperty("muted", True)
        status.addWidget(self.status_message, 1)
        status.addPermanentWidget(self.status_system)

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("Header")
        frame.setFixedHeight(68)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(QIcon(str(resource_path("assets/logo.svg"))).pixmap(38, 38))
        logo.setAccessibleName("CommMonit 标志")
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        brand = QLabel("COMMMONIT")
        brand.setObjectName("Brand")
        subtitle = QLabel("WINDOWS SERIAL I/O OBSERVER")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(brand)
        title_box.addWidget(subtitle)
        layout.addWidget(logo)
        layout.addLayout(title_box)
        layout.addStretch(1)

        self.theme_button = QPushButton("亮色模式" if self.theme == "dark" else "暗色模式")
        self.theme_button.setToolTip("切换面板亮色与暗色主题")
        self.theme_button.setAccessibleName("切换亮色和暗色主题")
        self.multi_button = QPushButton("软件多开")
        self.multi_button.setToolTip("启动一个独立的 CommMonit 新实例")
        self.multi_button.setAccessibleName("打开新的软件实例")
        self.privilege_badge = QLabel("用户态附加 · 无需驱动")
        self.privilege_badge.setStyleSheet(self._neutral_badge_style())
        self.connection_badge = QLabel("● 未连接")
        self.connection_badge.setStyleSheet(self._connection_badge_style(False))
        layout.addWidget(self.theme_button)
        layout.addWidget(self.multi_button)
        layout.addWidget(self.privilege_badge)
        layout.addWidget(self.connection_badge)
        return frame

    def _build_metrics(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)
        self.metric_state = MetricCard("监控状态", "待机")
        self.metric_events = MetricCard("捕获事件", "0")
        self.metric_rx = MetricCard("接收流量", "0 B")
        self.metric_tx = MetricCard("发送流量", "0 B")
        self.metric_rate = MetricCard("当前速率", "0 /s")
        for card in (self.metric_state, self.metric_events, self.metric_rx, self.metric_tx, self.metric_rate):
            layout.addWidget(card, 1)
        return layout

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setMinimumWidth(280)
        panel.setMaximumWidth(430)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        title_row = QHBoxLayout()
        title = QLabel("目标选择")
        title.setObjectName("SectionTitle")
        self.refresh_button = QToolButton()
        self.refresh_button.setText("刷新")
        self.refresh_button.setToolTip("刷新进程和串口设备（Ctrl+R）")
        self.refresh_button.setAccessibleName("刷新目标列表")
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self.refresh_button)
        layout.addLayout(title_row)

        tabs = QTabWidget()
        self.target_tabs = tabs
        process_tab = QWidget()
        process_layout = QVBoxLayout(process_tab)
        process_layout.setContentsMargins(8, 8, 8, 8)
        process_layout.setSpacing(8)
        self.process_search = QLineEdit()
        self.process_search.setPlaceholderText("筛选进程名称或 PID")
        self.process_search.setClearButtonEnabled(True)
        self.process_search.setAccessibleName("进程筛选")
        self.process_list = QListWidget()
        self.process_list.setAlternatingRowColors(True)
        self.process_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.process_list.setAccessibleName("可附加进程列表")
        process_layout.addWidget(self.process_search)
        process_layout.addWidget(self.process_list, 1)

        port_tab = QWidget()
        port_layout = QVBoxLayout(port_tab)
        port_layout.setContentsMargins(8, 8, 8, 8)
        port_layout.setSpacing(8)
        port_hint = QLabel("仅显示系统识别到的串口设备。为保证运行流畅，请在“进程”页选择目标并开始监控。")
        port_hint.setWordWrap(True)
        port_hint.setProperty("muted", True)
        self.port_list = QListWidget()
        self.port_list.setAlternatingRowColors(True)
        self.port_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.port_list.setAccessibleName("串口设备列表")
        port_layout.addWidget(port_hint)
        port_layout.addWidget(self.port_list, 1)

        tabs.addTab(process_tab, "进程")
        tabs.addTab(port_tab, "串口设备")
        tabs.setCurrentIndex(0)
        layout.addWidget(tabs, 1)

        self.selected_target = QLabel("尚未选择目标")
        self.selected_target.setWordWrap(True)
        self.selected_target.setProperty("muted", True)
        layout.addWidget(self.selected_target)

        button_row = QHBoxLayout()
        self.attach_button = QPushButton("开始监控")
        self.attach_button.setProperty("primary", True)
        self.attach_button.setEnabled(False)
        self.attach_button.setAccessibleName("附加并开始监控")
        self.stop_button = QPushButton("停止")
        self.stop_button.setProperty("danger", True)
        self.stop_button.setEnabled(False)
        self.stop_button.setAccessibleName("停止监控并分离")
        button_row.addWidget(self.attach_button, 1)
        button_row.addWidget(self.stop_button)
        layout.addLayout(button_row)

        note = QLabel("提示：建议以管理员身份运行。附加不会再次打开或占用串口。")
        note.setWordWrap(True)
        note.setProperty("muted", True)
        layout.addWidget(note)
        return panel

    def _build_capture_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        toolbar = QHBoxLayout()
        title = QLabel("数据流")
        title.setObjectName("SectionTitle")
        self.direction_filter = QComboBox()
        self.direction_filter.addItem("全部方向", "all")
        self.direction_filter.addItem("仅接收 RX", "rx")
        self.direction_filter.addItem("仅发送 TX", "tx")
        self.direction_filter.setAccessibleName("数据方向筛选")
        self.event_search = QLineEdit()
        self.event_search.setPlaceholderText("筛选 HEX、ASCII、端点…")
        self.event_search.setClearButtonEnabled(True)
        self.event_search.setMaximumWidth(280)
        self.event_search.setAccessibleName("捕获内容筛选")
        self.pause_button = QPushButton("暂停显示")
        self.pause_button.setCheckable(True)
        self.pause_button.setAccessibleName("暂停或恢复数据显示")
        self.clear_button = QPushButton("清空")
        self.export_button = QPushButton("导出")
        self.export_button.setAccessibleName("导出捕获记录")
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        toolbar.addWidget(self.direction_filter)
        toolbar.addWidget(self.event_search)
        toolbar.addWidget(self.pause_button)
        toolbar.addWidget(self.clear_button)
        toolbar.addWidget(self.export_button)
        layout.addLayout(toolbar)

        vertical_splitter = QSplitter(Qt.Vertical)
        vertical_splitter.setChildrenCollapsible(False)
        self.event_table = QTableView()
        self.event_table.setModel(self.proxy_model)
        self.event_table.setAlternatingRowColors(True)
        self.event_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.event_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.event_table.setSortingEnabled(False)
        self.event_table.verticalHeader().setVisible(False)
        self.event_table.verticalHeader().setDefaultSectionSize(31)
        self.event_table.setWordWrap(False)
        self.event_table.setAccessibleName("串口收发事件表")
        header = self.event_table.horizontalHeader()
        header.setMinimumHeight(32)
        header_font = header.font()
        header_font.setBold(True)
        header.setFont(header_font)
        for column in (0, 1, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.Stretch)
        self.event_table.setColumnWidth(2, 130)
        vertical_splitter.addWidget(self.event_table)

        detail_panel = QWidget()
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 6, 0, 0)
        detail_layout.setSpacing(7)
        detail_header = QHBoxLayout()
        detail_title = QLabel("帧详情")
        detail_title.setObjectName("SectionTitle")
        self.detail_meta = QLabel("选择一条记录查看完整数据")
        self.detail_meta.setProperty("muted", True)
        self.copy_button = QPushButton("复制完整 HEX")
        self.copy_button.setEnabled(False)
        detail_header.addWidget(detail_title)
        detail_header.addWidget(self.detail_meta)
        detail_header.addStretch(1)
        detail_header.addWidget(self.copy_button)
        self.detail_view = QPlainTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setPlaceholderText("完整的十六进制与 ASCII 数据将在这里显示")
        self.detail_view.setAccessibleName("选中帧的完整数据")
        detail_layout.addLayout(detail_header)
        detail_layout.addWidget(self.detail_view)
        vertical_splitter.addWidget(detail_panel)
        vertical_splitter.setSizes([560, 185])
        layout.addWidget(vertical_splitter, 1)
        return panel

    def _wire_events(self) -> None:
        self.refresh_button.clicked.connect(self.refresh_inventory)
        self.theme_button.clicked.connect(self.toggle_theme)
        self.multi_button.clicked.connect(self.open_new_instance)
        self.process_search.textChanged.connect(self._filter_processes)
        self.process_list.itemSelectionChanged.connect(self._on_process_selected)
        self.process_list.itemDoubleClicked.connect(lambda _item: self.attach_selected())
        self.target_tabs.currentChanged.connect(self._on_target_mode_changed)
        self.attach_button.clicked.connect(self.attach_selected)
        self.stop_button.clicked.connect(lambda: self.controller.detach())
        self.direction_filter.currentIndexChanged.connect(
            lambda _index: self.proxy_model.set_direction(str(self.direction_filter.currentData()))
        )
        self.event_search.textChanged.connect(self.proxy_model.set_query)
        self.pause_button.toggled.connect(self._toggle_pause)
        self.clear_button.clicked.connect(self.clear_events)
        self.export_button.clicked.connect(self.export_events)
        self.event_table.selectionModel().selectionChanged.connect(self._update_detail)
        self.copy_button.clicked.connect(self._copy_selected_hex)

        self.controller.event_received.connect(self._on_event)
        self.controller.attached.connect(self._on_attached)
        self.controller.target_detached.connect(self._on_target_detached)
        self.controller.detached.connect(self._on_detached)
        self.controller.port_closed.connect(self._on_port_closed)
        self.controller.session_count_changed.connect(self._on_session_count_changed)
        self.controller.error.connect(self._on_error)
        self.controller.diagnostic.connect(self._on_diagnostic)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence.Refresh, self, activated=self.refresh_inventory)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_events)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.clear_events)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.event_search.setFocus)

    def _apply_palette_roles(self) -> None:
        for frame in self.findChildren(QFrame):
            if frame.objectName() in ("MetricCard", "Panel"):
                frame.setBackgroundRole(QPalette.Base)
                frame.setAutoFillBackground(True)
            elif frame.objectName() == "Header":
                frame.setBackgroundRole(QPalette.AlternateBase)
                frame.setAutoFillBackground(True)
        for label in self.findChildren(QLabel):
            if label.property("muted") or label.objectName() in ("Subtitle", "MetricLabel"):
                label.setForegroundRole(QPalette.PlaceholderText)
        for line_edit in self.findChildren(QLineEdit):
            line_edit.setMinimumHeight(34)
        for combo_box in self.findChildren(QComboBox):
            combo_box.setMinimumHeight(34)
        self.statusBar().setBackgroundRole(QPalette.AlternateBase)
        self.statusBar().setAutoFillBackground(True)

    def toggle_theme(self) -> None:
        self.theme = "light" if self.theme == "dark" else "dark"
        self.setUpdatesEnabled(False)
        app = QApplication.instance()
        target_palette = palette_for_theme(self.theme)
        app.setPalette(target_palette)
        self.setPalette(target_palette)
        for widget in self.findChildren(QWidget):
            widget.setPalette(target_palette)
        QSettings("CommMonit", "CommMonit").setValue("theme", self.theme)
        self.event_model.set_theme(self.theme)
        self.theme_button.setText("暗色模式" if self.theme == "light" else "亮色模式")
        self.privilege_badge.setStyleSheet(self._neutral_badge_style())
        self.connection_badge.setStyleSheet(
            self._connection_badge_style(self.controller.is_attached or self.demo)
        )
        self.setUpdatesEnabled(True)
        self.update()
        self.status_message.setText("已切换为亮色主题" if self.theme == "light" else "已切换为暗色主题")

    def open_new_instance(self) -> None:
        if getattr(sys, "frozen", False):
            program = sys.executable
            arguments = ["--new-instance"]
        else:
            program = sys.executable
            arguments = [str(Path(__file__).resolve().parent.parent / "main.py"), "--new-instance"]
        result = QProcess.startDetached(program, arguments)
        started = result[0] if isinstance(result, tuple) else bool(result)
        if started:
            self.status_message.setText("已启动新的 CommMonit 实例")
        else:
            QMessageBox.critical(self, "软件多开失败", "无法启动新的 CommMonit 实例。")

    def _neutral_badge_style(self) -> str:
        if self.theme == "light":
            return (
                "padding: 6px 10px; color: #44515E; background: #E5EAF0;"
                "border: 1px solid #AAB6C1; border-radius: 4px; font-weight: 600;"
            )
        return (
            "padding: 6px 10px; color: #AAB6C3; background: #17202A;"
            "border: 1px solid #344252; border-radius: 4px; font-weight: 600;"
        )

    def _connection_badge_style(self, active: bool) -> str:
        if self.theme == "light":
            if active:
                return (
                    "padding: 6px 11px; color: #17633F; background: #DDF3E8;"
                    "border: 1px solid #73B493; border-radius: 4px; font-weight: 700;"
                )
            return (
                "padding: 6px 11px; color: #5D6975; background: #E9EDF1;"
                "border: 1px solid #AAB6C1; border-radius: 4px; font-weight: 700;"
            )
        if active:
            return (
                "padding: 6px 11px; color: #9FE7C2; background: #13251F;"
                "border: 1px solid #34765B; border-radius: 4px; font-weight: 700;"
            )
        return (
            "padding: 6px 11px; color: #9AA8B7; background: #141B23;"
            "border: 1px solid #344252; border-radius: 4px; font-weight: 700;"
        )

    def refresh_inventory(self) -> None:
        selected_pid = self._selected_pid()
        self.refresh_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._processes = list_processes()
            self.process_list.clear()
            for process in self._processes:
                item = QListWidgetItem(f"{process.name}\nPID {process.pid} · {process.username}")
                item.setData(Qt.UserRole, process.pid)
                item.setToolTip(process.executable or process.name)
                self.process_list.addItem(item)
                if process.pid == selected_pid:
                    item.setSelected(True)
            self.port_list.clear()
            ports = list_serial_ports()
            if ports:
                for port in ports:
                    item = QListWidgetItem(f"{port.device}\n{port.description}")
                    item.setData(Qt.UserRole, port.device)
                    item.setToolTip(port.hardware_id)
                    self.port_list.addItem(item)
            else:
                item = QListWidgetItem("未检测到串口设备")
                item.setFlags(Qt.NoItemFlags)
                self.port_list.addItem(item)
            self.status_message.setText(f"已发现 {len(self._processes)} 个可见进程 · {len(ports)} 个串口设备")
            self._filter_processes(self.process_search.text())
            self._update_attach_action()
        finally:
            QApplication.restoreOverrideCursor()
            self.refresh_button.setEnabled(True)

    def _filter_processes(self, text: str) -> None:
        query = text.strip().lower()
        for index in range(self.process_list.count()):
            item = self.process_list.item(index)
            item.setHidden(bool(query) and query not in item.text().lower())

    def _on_process_selected(self) -> None:
        pid = self._selected_pid()
        process = next((item for item in self._processes if item.pid == pid), None)
        if process:
            self.selected_target.setText(f"目标：{process.name} · PID {process.pid}")
            self._target_name = process.name
        else:
            self.selected_target.setText("尚未选择目标")
        self._update_attach_action()

    def _on_target_mode_changed(self, index: int) -> None:
        if index == 0:
            self._on_process_selected()
        else:
            self.selected_target.setText("串口设备信息仅供查看")
            self._update_attach_action()

    def _selected_pid(self) -> int | None:
        items = self.process_list.selectedItems()
        return int(items[0].data(Qt.UserRole)) if items else None

    def _update_attach_action(self) -> None:
        if self.target_tabs.currentIndex() == 0:
            pid = self._selected_pid()
            self.attach_button.setText("监控所选进程")
            self.attach_button.setEnabled(pid is not None and pid not in self.controller.pids)
        else:
            self.attach_button.setText("设备信息")
            self.attach_button.setEnabled(False)

    def attach_selected(self) -> None:
        if self.target_tabs.currentIndex() == 1:
            return
        pid = self._selected_pid()
        if pid is None:
            return
        self.status_message.setText(f"正在附加到 PID {pid}…")
        self.attach_button.setEnabled(False)
        QApplication.processEvents()
        self.controller.attach(pid)

    def _on_attached(self, pid: int) -> None:
        self.status_message.setText(f"PID {pid} 已连接，等待串口读写")
        self._on_session_count_changed(self.controller.session_count)

    def _on_target_detached(self, pid: int, reason: str) -> None:
        self.status_message.setText(f"PID {pid} · {reason}")

    def _on_port_closed(self, _pid: int, _handle: str, endpoint: str) -> None:
        self.status_message.setText(f"{endpoint} 已关闭，对应监控已自动停止")
        self._update_attach_action()

    def _on_session_count_changed(self, count: int) -> None:
        endpoint_count = self.controller.active_endpoint_count
        active = count > 0
        self.stop_button.setEnabled(active)
        self.metric_state.set_value("监控中" if active else "待机")
        if active:
            self.connection_badge.setText(f"● {endpoint_count} 串口 · {count} 进程")
        else:
            self.connection_badge.setText("● 未连接")
        self.connection_badge.setStyleSheet(self._connection_badge_style(active))
        self._update_attach_action()

    def _on_detached(self, reason: str) -> None:
        self._on_session_count_changed(0)
        self.status_message.setText(reason)

    def _on_error(self, message: str) -> None:
        self._update_attach_action()
        QMessageBox.critical(self, "无法开始监控", message)

    def _on_diagnostic(self, message: str) -> None:
        self.status_message.setText(message)

    def _on_event(self, event: CaptureEvent) -> None:
        if self._paused:
            self._paused_events.append(event)
        else:
            self.event_model.append_event(event)
            self.event_table.scrollToBottom()
        if event.direction == "rx":
            self._rx_bytes += len(event.data)
        else:
            self._tx_bytes += len(event.data)
        self._event_times.append(datetime.now().timestamp())

    def _toggle_pause(self, paused: bool) -> None:
        self._paused = paused
        self.pause_button.setText("恢复显示" if paused else "暂停显示")
        if paused:
            self.metric_state.set_value("已暂停")
            self.status_message.setText("显示已暂停，后台仍在捕获数据")
        else:
            if self._paused_events:
                queued = self._paused_events
                self._paused_events = []
                self.event_model.append_events(queued)
                self.event_table.scrollToBottom()
            self.metric_state.set_value("监控中" if self.controller.is_attached else "待机")
            self.status_message.setText("显示已恢复")

    def clear_events(self) -> None:
        self.event_model.clear()
        self._paused_events.clear()
        self._event_times.clear()
        self._rx_bytes = 0
        self._tx_bytes = 0
        self.detail_view.clear()
        self.detail_meta.setText("选择一条记录查看完整数据")
        self.copy_button.setEnabled(False)
        self.status_message.setText("捕获记录已清空")

    def export_events(self) -> None:
        events = [*self.event_model.events, *self._paused_events]
        if not events:
            QMessageBox.information(self, "没有可导出的数据", "开始监控并捕获数据后再导出。")
            return
        default_name = f"CommMonit_{datetime.now():%Y%m%d_%H%M%S}.csv"
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "导出串口捕获",
            str(Path.home() / "Desktop" / default_name),
            "CSV 表格 (*.csv);;JSON 数据 (*.json)",
        )
        if not path:
            return
        try:
            if selected_filter.startswith("JSON") or path.lower().endswith(".json"):
                if not path.lower().endswith(".json"):
                    path += ".json"
                export_json(path, events)
            else:
                if not path.lower().endswith(".csv"):
                    path += ".csv"
                export_csv(path, events)
            self.status_message.setText(f"已导出 {len(events)} 条记录 · {path}")
        except OSError as exc:
            QMessageBox.critical(self, "导出失败", f"无法写入文件：{exc}")

    def _update_detail(self) -> None:
        indexes = self.event_table.selectionModel().selectedRows()
        if not indexes:
            self.detail_view.clear()
            self.copy_button.setEnabled(False)
            return
        source_index = self.proxy_model.mapToSource(indexes[0])
        event = self.event_model.events[source_index.row()]
        self.detail_meta.setText(
            f"{event.direction_label} · {event.endpoint} · PID {event.process_id or '—'} · "
            f"{event.baud_rate or '未知波特率'} {event.frame} · {len(event.data)} 字节"
        )
        self.detail_view.setPlainText(_hexdump(event.data))
        self.copy_button.setEnabled(True)

    def _copy_selected_hex(self) -> None:
        indexes = self.event_table.selectionModel().selectedRows()
        if not indexes:
            return
        source_index = self.proxy_model.mapToSource(indexes[0])
        event = self.event_model.events[source_index.row()]
        QApplication.clipboard().setText(format_hex(event.data))
        self.status_message.setText("完整 HEX 已复制到剪贴板")

    def _update_metrics(self) -> None:
        now = datetime.now().timestamp()
        while self._event_times and self._event_times[0] < now - 1.0:
            self._event_times.popleft()
        total = len(self.event_model.events) + len(self._paused_events)
        self.metric_events.set_value(f"{total:,}")
        self.metric_rx.set_value(format_size(self._rx_bytes))
        self.metric_tx.set_value(format_size(self._tx_bytes))
        self.metric_rate.set_value(f"{len(self._event_times)} /s")

    def _start_demo(self) -> None:
        self._target_name = "IndustrialController.exe"
        self.connection_badge.setText("● 演示模式")
        self.connection_badge.setStyleSheet(self._connection_badge_style(True))
        self.metric_state.set_value("演示")
        demo_frames = [
            ("tx", b"\x01\x03\x00\x00\x00\x0A\xC5\xCD"),
            ("rx", b"\x01\x03\x14\x00\xE8\x00\x07\x00\x11\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x4E\x4A"),
            ("tx", b"AT+STATUS?\r\n"),
            ("rx", b"+STATUS:RUN,24.7C,68%\r\nOK\r\n"),
        ]
        for index in range(18):
            direction, data = demo_frames[index % len(demo_frames)]
            self._on_event(
                CaptureEvent(
                    timestamp=datetime.now(),
                    direction=direction,
                    endpoint="COM3",
                    data=data,
                    baud_rate=115200,
                    frame="8N1",
                    process_id=4248,
                )
            )

        timer = QTimer(self)
        timer.timeout.connect(
            lambda: self._on_event(
                CaptureEvent(
                    timestamp=datetime.now(),
                    direction="rx" if random.random() > 0.4 else "tx",
                    endpoint="COM3",
                    data=os.urandom(random.randint(4, 16)),
                    baud_rate=115200,
                    frame="8N1",
                    process_id=4248,
                )
            )
        )
        timer.start(900)
        self.demo_timer = timer
        QTimer.singleShot(
            300,
            lambda: self.process_list.setCurrentRow(0) if self.process_list.count() else None,
        )

    def closeEvent(self, event) -> None:
        self.controller.detach("程序关闭")
        event.accept()


def _hexdump(data: bytes, width: int = 16) -> str:
    lines: list[str] = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        hex_part = " ".join(f"{value:02X}" for value in chunk).ljust(width * 3 - 1)
        ascii_part = "".join(chr(value) if 32 <= value <= 126 else "·" for value in chunk)
        lines.append(f"{offset:08X}  {hex_part}  │{ascii_part}│")
    return "\n".join(lines)


def _escape_label(value: str) -> str:
    return value.replace("&", "&&")
