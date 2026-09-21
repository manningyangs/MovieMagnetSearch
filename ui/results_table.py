"""结果表格：QTableView + 自定义模型，支持排序、右键菜单、复制磁链。"""
from __future__ import annotations

import urllib.parse
from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QAction, QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QStyle,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from core.models import TorrentResult, Resolution
from utils.magnet import format_size


HEADERS = [
    "排名",
    "标题",
    "来源",
    "分辨率",
    "大小",
    "做种",
    "下载",
    "发布时间",
    "评分",
]


class ResultsModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._rows: List[TorrentResult] = []

    def set_rows(self, rows: List[TorrentResult]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return str(index.row() + 1)
            if col == 1:
                return row.title
            if col == 2:
                return row.source
            if col == 3:
                return row.resolution.value
            if col == 4:
                return row.size_display
            if col == 5:
                return str(row.seeders)
            if col == 6:
                return str(row.leechers)
            if col == 7:
                return row.upload_date.strftime("%Y-%m-%d") if row.upload_date else "未知"
            if col == 8:
                return f"{row.score:.1f}"
        elif role == Qt.ToolTipRole and col == 1:
            return row.title
        elif role == Qt.TextAlignmentRole:
            if col in (0, 3, 4, 5, 6, 7, 8):
                return int(Qt.AlignCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        elif role == Qt.ForegroundRole and col == 8:
            score = row.score
            if score >= 70:
                return QColor("#2e7d32")  # 绿
            if score >= 40:
                return QColor("#f57f17")  # 黄
            return QColor("#c62828")  # 红
        return None

    def get_row(self, row: int) -> Optional[TorrentResult]:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    @property
    def rows(self) -> List[TorrentResult]:
        return self._rows

    def sort(self, column: int, order=Qt.AscendingOrder) -> None:
        if not self._rows:
            return
        reverse = order == Qt.DescendingOrder
        # 列 → 排序键
        def key(r: TorrentResult):
            if column == 1:
                return r.title.lower()
            if column == 2:
                return r.source.lower()
            if column == 3:
                return r.resolution.score  # 用分值排序更合理
            if column == 4:
                return r.size_bytes
            if column == 5:
                return r.seeders
            if column == 6:
                return r.leechers
            if column == 7:
                return r.upload_date or datetime.min
            if column == 8:
                return r.score
            return 0
        self.layoutAboutToBeChanged.emit()
        self._rows.sort(key=key, reverse=reverse)
        self.layoutChanged.emit()


class ResultsTable(QWidget):
    """结果表格容器：标题提示 + 表格视图。"""

    copy_requested = Signal(str)  # 发出要复制的磁力链接

    def __init__(self) -> None:
        super().__init__()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        hint = QLabel("双击行复制磁力链接 · 右键更多操作 · 点击表头排序")
        hint.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(hint)

        # 分辨率过滤栏
        from PySide6.QtWidgets import QCheckBox
        filter_row = QHBoxLayout()
        filter_row.setSpacing(12)
        filter_lbl = QLabel("分辨率过滤:")
        filter_lbl.setStyleSheet("color: #666;")
        filter_row.addWidget(filter_lbl)
        self._all_rows: List[TorrentResult] = []
        self.chk_filters = {}
        for res in ("4K", "1080p", "720p", "其他"):
            chk = QCheckBox(res)
            chk.setChecked(False)  # 默认全选（不过滤）
            chk.stateChanged.connect(self._apply_filter)
            filter_row.addWidget(chk)
            self.chk_filters[res] = chk
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        self.view = QTableView()
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.setAlternatingRowColors(True)
        self.view.verticalHeader().setVisible(False)
        self.view.setShowGrid(False)
        self.view.horizontalHeader().setStretchLastSection(False)
        self.view.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.view.horizontalHeader().setDefaultSectionSize(70)
        self.view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.view.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.view.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.view.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.view.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.view.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.view.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.view.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)

        self.model = ResultsModel()
        self.view.setModel(self.model)
        self.view.setSortingEnabled(True)
        self.view.doubleClicked.connect(self._on_double_click)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.view)

    def set_results(self, results: List[TorrentResult]) -> None:
        self._all_rows = list(results)
        self.model.set_rows(results)
        self.view.resizeColumnsToContents()
        self.view.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

    def _apply_filter(self) -> None:
        if not self._all_rows:
            return
        checked = {res for res, chk in self.chk_filters.items() if chk.isChecked()}
        if not checked:
            # 无勾选 = 显示全部
            self.model.set_rows(self._all_rows)
            return
        def match(r: TorrentResult) -> bool:
            val = r.resolution.value
            if val in checked:
                return True
            if "其他" in checked and val not in ("4K", "1080p", "720p"):
                return True
            return False
        self.model.set_rows([r for r in self._all_rows if match(r)])
        self.view.resizeColumnsToContents()
        self.view.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

    def _current_result(self) -> Optional[TorrentResult]:
        idx = self.view.currentIndex()
        if not idx.isValid():
            return None
        return self.model.get_row(idx.row())

    def _on_double_click(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        row = self.model.get_row(index.row())
        if row:
            self._copy_magnet(row.magnet_link)

    def _on_context_menu(self, pos) -> None:
        index = self.view.indexAt(pos)
        if not index.isValid():
            return
        row = self.model.get_row(index.row())
        if not row:
            return
        menu = QMenu(self.view)
        act_copy = QAction("复制磁力链接", self.view)
        act_copy.triggered.connect(lambda: self._copy_magnet(row.magnet_link))
        act_hash = QAction("复制 info_hash", self.view)
        act_hash.triggered.connect(lambda: self._copy_magnet(row.info_hash))
        act_open = QAction("打开来源页面", self.view)
        act_open.triggered.connect(lambda: self._open_url(row.detail_url))
        menu.addAction(act_copy)
        menu.addAction(act_hash)
        menu.addAction(act_open)
        menu.exec(self.view.viewport().mapToGlobal(pos))

    def _copy_magnet(self, text: str) -> None:
        clip = QApplication.clipboard()
        clip.setText(text)
        self.copy_requested.emit(text)

    def _open_url(self, url: str) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        if url:
            QDesktopServices.openUrl(QUrl(url))
