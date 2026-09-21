"""主窗口：搜索栏 + 结果展示（电影/剧集双模式）+ 进度提示 + 状态栏。"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import AppConfig
from core.models import TorrentResult
from core.search_manager import SearchManager
from utils.episode import parse_episode
from ui.results_table import ResultsTable
from ui.settings_dialog import SettingsDialog


MODE_LABELS = {
    "movie": "电影",
    "tv": "剧集综艺",
}


class SearchLineEdit(QLineEdit):
    """搜索输入框：中文输入法组字期间的回车只用于确认候选字，不触发搜索。

    通过 event.ignore() 把按键放行到 Windows DefWindowProc，IME 才能正常
    提交候选字并结束组字；绝不能直接吞掉，否则输入法状态机错乱。
    """

    # 提交候选字后，IME 可能仍残余一个回车事件，该时间窗口内的回车视为确认键
    _COMMIT_GRACE = 0.3

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._composing = False
        self._last_commit = -1.0

    def inputMethodEvent(self, event) -> None:
        self._composing = bool(event.preeditString())
        if event.commitString():
            self._last_commit = time.monotonic()
        super().inputMethodEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            input_method = QApplication.inputMethod()
            ime_visible = input_method is not None and input_method.isVisible()
            recent_commit = time.monotonic() - self._last_commit < self._COMMIT_GRACE
            if self._composing or ime_visible or recent_commit:
                event.ignore()
                return
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.setWindowTitle("磁力链接搜索工具")
        self.resize(config.window_width, config.window_height)
        self._mode = "movie"

        self.search_manager = SearchManager(self.config)
        self.search_manager.search_started.connect(self._on_search_started)
        self.search_manager.source_progress.connect(self._on_source_progress)
        self.search_manager.source_finished.connect(self._on_source_finished)
        self.search_manager.search_finished.connect(self._on_search_finished)
        self.search_manager.search_failed.connect(self._on_search_failed)
        self._total_sources = 0

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # 搜索栏
        bar = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("电影", "movie")
        self.mode_combo.addItem("剧集 / 综艺", "tv")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.input = SearchLineEdit()
        self.input.setPlaceholderText("输入电影名称，回车搜索…")
        self.input.returnPressed.connect(self._do_search)
        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self._do_search)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_search)
        self.settings_btn = QPushButton("设置")
        self.settings_btn.clicked.connect(self._open_settings)
        bar.addWidget(QLabel("类型:"))
        bar.addWidget(self.mode_combo)
        bar.addWidget(self.input, 1)
        bar.addWidget(self.search_btn)
        bar.addWidget(self.stop_btn)
        bar.addWidget(self.settings_btn)
        root.addLayout(bar)

        # 搜索进度提示
        prog_row = QHBoxLayout()
        self.progress_label = QLabel("就绪。输入片名开始搜索。")
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(240)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        prog_row.addWidget(self.progress_label, 1)
        prog_row.addWidget(self.progress_bar)
        root.addLayout(prog_row)

        # 结果区：用叠层切换表格 vs 分组树
        from PySide6.QtWidgets import QStackedLayout
        self.results_stack = QWidget()
        self._stack = QStackedLayout(self.results_stack)

        # 电影模式：现有 ResultsTable
        self.table = ResultsTable()
        self._stack.addWidget(self.table)

        # TV 模式：QTreeWidget 分组展示
        self.tree = self._build_tv_tree()
        self._stack.addWidget(self.tree)

        self._stack.setCurrentIndex(0)  # 默认电影
        root.addWidget(self.results_stack, 1)

        # 状态栏
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("就绪。输入片名开始搜索。")

    def _build_tv_tree(self) -> QTreeWidget:
        from PySide6.QtWidgets import QHeaderView
        tree = QTreeWidget()
        tree.setHeaderLabels(["剧集分组", "标题", "来源", "分辨率", "大小", "做种", "评分"])
        tree.header().setStretchLastSection(False)
        h = tree.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        tree.setAlternatingRowColors(True)
        tree.setUniformRowHeights(True)
        tree.setContextMenuPolicy(Qt.CustomContextMenu)
        tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        tree.itemDoubleClicked.connect(self._on_tree_double_clicked)
        return tree

    def _on_mode_changed(self, _idx: int) -> None:
        mode = self.mode_combo.currentData()
        self._mode = mode
        if mode == "movie":
            self.input.setPlaceholderText("输入电影名称，回车搜索…")
            self._stack.setCurrentIndex(0)
        else:
            self.input.setPlaceholderText("输入剧集/综艺名（如《绝命毒师》、《奇葩说》）…")
            self._stack.setCurrentIndex(1)
        self.progress_label.setText("就绪。输入片名开始搜索。")
        self.table.set_results([])
        self.tree.clear()

    # ---------- 搜索 ----------
    def _do_search(self) -> None:
        query = self.input.text().strip()
        if not query:
            return
        mode = self.mode_combo.currentData()
        self._mode = mode
        if mode == "movie":
            self.table.set_results([])
        else:
            self.tree.clear()
        self._set_search_running(True)
        self.status.showMessage(f"正在搜索({MODE_LABELS[mode]}): {query} …")
        self.search_manager.search(query, mode=mode)

    def _stop_search(self) -> None:
        self.search_manager.stop()

    def _set_search_running(self, running: bool) -> None:
        """统一管理各按钮的启用/禁用状态。"""
        self.search_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.input.setEnabled(not running)
        self.mode_combo.setEnabled(not running)
        self.settings_btn.setEnabled(not running)

    def _on_search_started(self, total: int) -> None:
        self._total_sources = total
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("已完成 %v/%m 个源")
        self.progress_bar.setTextVisible(True)
        self.progress_label.setText(f"正在搜索: {self.input.text().strip()} …（0/{total} 个源完成）")

    def _on_source_progress(self, done: int, total: int) -> None:
        self._total_sources = total
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(done)
        self.progress_label.setText(f"搜索中… 已完成 {done}/{total} 个搜索源")

    def _on_source_finished(self, name: str, count: int, error: str) -> None:
        if error:
            self.status.showMessage(f"{name} 失败: {error}")
        else:
            self.status.showMessage(f"{name} 完成，命中 {count} 条")

    def _on_search_finished(self, results: List[TorrentResult]) -> None:
        self._set_search_running(False)
        self.progress_bar.setValue(self._total_sources)
        self.progress_bar.setFormat("完成")
        if self._mode == "movie":
            self.table.set_results(results)
            self.progress_label.setText(
                f"搜索完成，共 {len(results)} 条结果（已按质量排序）"
            )
            self.status.showMessage(f"搜索完成，共 {len(results)} 条结果（已按质量排序）")
        else:
            self._populate_tv_tree(results)
            self.progress_label.setText(
                f"搜索完成，共 {len(results)} 条，已按剧集分组"
            )
            self.status.showMessage(f"搜索完成，共 {len(results)} 条，已按剧集分组")

    def _on_search_failed(self, msg: str) -> None:
        self._set_search_running(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_label.setText(f"搜索失败: {msg}")
        self.status.showMessage(f"搜索失败: {msg}")

    # ---------- TV 分组 ----------
    def _populate_tv_tree(self, results: List[TorrentResult]) -> None:
        self.tree.clear()
        # 按 group_key 分组
        groups: Dict[str, List[TorrentResult]] = defaultdict(list)
        for r in results:
            parsed = parse_episode(r.title)
            if parsed:
                groups[parsed["group_key"]].append(r)
            else:
                groups["未分类"].append(r)

        # 组排序：先按 S01E05 之类的自然序，再按条目分
        def group_sort_key(name: str):
            if name == "未分类":
                return (9999, 9999, name)
            # 尝试解析 SxxEyy
            import re
            m = re.match(r"S(\d+)E(\d+)", name, re.IGNORECASE)
            if m:
                return (int(m.group(1)), int(m.group(2)), name)
            m = re.match(r"S(\d+)\s+Complete", name, re.IGNORECASE)
            if m:
                return (int(m.group(1)), 999, name)
            if name == "Complete Series":
                return (9998, 0, name)
            return (0, 0, name)

        for group_name in sorted(groups.keys(), key=group_sort_key):
            torrents = groups[group_name]
            torrents.sort(key=lambda r: (-r.score, -r.seeders))
            parent = QTreeWidgetItem(self.tree)
            label = f"{group_name}  ·  {len(torrents)} 条"
            parent.setText(0, label)
            parent.setData(0, Qt.UserRole, group_name)
            parent.setExpanded(True)
            parent.setFlags(parent.flags() & ~Qt.ItemIsSelectable)
            # 父节点禁用选择：点击不高亮
            parent.setForeground(0, QColor("#1565c0"))
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)

            for r in torrents:
                child = QTreeWidgetItem(parent)
                child.setData(0, Qt.UserRole, r)
                child.setText(1, r.title)
                child.setText(2, r.source)
                child.setText(3, r.resolution.value)
                child.setText(4, r.size_display)
                child.setText(5, str(r.seeders))
                child.setText(6, f"{r.score:.1f}")
                child.setToolTip(1, r.title)
                # 评分颜色
                score = r.score
                color = QColor("#2e7d32") if score >= 70 else (
                    QColor("#f57f17") if score >= 40 else QColor("#c62828")
                )
                child.setForeground(6, color)

        self.tree.expandAll()

    def _on_tree_double_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        data = item.data(0, Qt.UserRole)
        if not isinstance(data, TorrentResult):
            return
        self._copy_magnet(data.magnet_link)

    def _on_tree_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return
        data = item.data(0, Qt.UserRole)
        if not isinstance(data, TorrentResult):
            return
        from PySide6.QtWidgets import QAction, QMenu
        menu = QMenu(self.tree)
        act_copy = QAction("复制磁力链接", self.tree)
        act_copy.triggered.connect(lambda: self._copy_magnet(data.magnet_link))
        act_hash = QAction("复制 info_hash", self.tree)
        act_hash.triggered.connect(lambda: self._copy_magnet(data.info_hash))
        act_open = QAction("打开来源页面", self.tree)
        act_open.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(data.detail_url)))
        menu.addAction(act_copy)
        menu.addAction(act_hash)
        menu.addAction(act_open)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _copy_magnet(self, text: str) -> None:
        clip = QApplication.clipboard()
        clip.setText(text)
        self.status.showMessage("磁力链接已复制到剪贴板")

    # ---------- 设置 ----------
    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            self.config.save()
            self.search_manager.reload_config(self.config)

    def closeEvent(self, event) -> None:
        self.config.window_width = self.width()
        self.config.window_height = self.height()
        self.config.save()
        super().closeEvent(event)
