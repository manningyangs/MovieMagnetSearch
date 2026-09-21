"""豆瓣发现 Tab：Top250 榜单 + 关键词搜索 + 卡片列表。"""
from __future__ import annotations

import hashlib
import os
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, QSize, QThread, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.douban import DoubanClient, DoubanMovie


COVER_CACHE_DIR = os.path.join(
    os.path.expanduser("~"), ".movie_search", "cache", "covers"
)


# ---------- 异步加载 Top250 / 搜索 ----------

class DoubanLoadWorker(QObject):
    """后台线程跑豆瓣请求。"""
    finished = Signal(list, str)      # (items, error)
    progress = Signal(int, int)       # (done, total) — Top250 页数

    def __init__(self, action: str, query: str = "") -> None:
        super().__init__()
        self.action = action   # "top250" or "search"
        self.query = query

    @Slot()
    def run(self) -> None:
        client = DoubanClient()
        try:
            if self.action == "top250":
                items = client.get_top250(limit=250)
                self.finished.emit(items, "")
            elif self.action == "search":
                items = client.search(self.query, max_results=30)
                self.finished.emit(items, "")
            else:
                self.finished.emit([], "未知操作")
        except Exception as e:
            self.finished.emit([], f"{type(e).__name__}: {e}")


# ---------- 封面异步加载 + 本地缓存 ----------

class CoverLoader(QObject):
    """异步下载封面图并通过信号投递 QPixmap。"""
    cover_loaded = Signal(str, QPixmap)   # (douban_id, pixmap)

    def __init__(self) -> None:
        super().__init__()
        os.makedirs(COVER_CACHE_DIR, exist_ok=True)

    def cached_path(self, douban_id: str) -> str:
        return os.path.join(COVER_CACHE_DIR, f"{douban_id}.jpg")

    @Slot(str, str)
    def load(self, douban_id: str, url: str) -> None:
        if not douban_id or not url:
            return
        local = self.cached_path(douban_id)
        if os.path.exists(local):
            pm = QPixmap(local)
            if not pm.isNull():
                self.cover_loaded.emit(douban_id, pm)
                return
        try:
            import requests as req
            s = req.Session()
            s.trust_env = False
            r = s.get(url, headers={
                "User-Agent": "Mozilla/5.0 Chrome/120.0.0.0",
                "Referer": "https://movie.douban.com/",
            }, timeout=15)
            r.raise_for_status()
            with open(local, "wb") as f:
                f.write(r.content)
            pm = QPixmap(local)
            if not pm.isNull():
                self.cover_loaded.emit(douban_id, pm)
        except Exception as e:
            # 缓存一个占位文件避免反复失败
            open(local, "w").close()


# ---------- 单个电影卡片 ----------

class MovieCard(QWidget):
    """横向卡片：封面 + 标题 + 评分 + 导演 + 简介 + 操作按钮。"""
    search_requested = Signal(str)    # 告诉主窗口去磁力搜索这个标题
    open_requested = Signal(str)      # 打开豆瓣详情页

    COVER_W = 120
    COVER_H = 170

    def __init__(self, movie: DoubanMovie, loader: CoverLoader, parent=None) -> None:
        super().__init__(parent)
        self.movie = movie
        self._loader = loader
        self.setFixedHeight(self.COVER_H + 20)
        self._build_ui()
        # 请求封面
        if movie.douban_id:
            loader.cover_loaded.connect(self._on_cover_loaded)
            loader.load(movie.douban_id, movie.cover_url)

    def _build_ui(self) -> None:
        from PySide6.QtWidgets import QHBoxLayout
        from PySide6.QtGui import QFont

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        # 封面占位（用一个带边框的 QLabel）
        self.cover_label = QLabel("封面")
        self.cover_label.setFixedSize(self.COVER_W, self.COVER_H)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet(
            "background-color: #f0f0f0; border: 1px solid #ddd; color: #999;"
        )
        root.addWidget(self.cover_label)

        # 右侧文本区
        right = QVBoxLayout()
        right.setSpacing(4)

        # 标题行：排名 + 标题 + 评分
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        if self.movie.rank:
            rank_label = QLabel(f"#{self.movie.rank}")
            rank_label.setStyleSheet("color: #c00; font-weight: bold; font-size: 16px;")
            title_row.addWidget(rank_label)

        title = self.movie.title
        if self.movie.original_title and self.movie.original_title != title:
            title += f"  /  {self.movie.original_title}"
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setWordWrap(True)
        title_row.addWidget(title_label, 1)

        rating = self.movie.rating
        if rating > 0:
            rating_label = QLabel(f"★ {rating:.1f}")
            rating_label.setStyleSheet("color: #e07b00; font-weight: bold; font-size: 14px;")
            title_row.addWidget(rating_label)

        year_label = QLabel(self.movie.year)
        year_label.setStyleSheet("color: #888;")
        title_row.addWidget(year_label)

        right.addLayout(title_row)

        # 导演 + 主演
        info_parts = []
        if self.movie.directors:
            info_parts.append(f"导演: {' / '.join(self.movie.directors[:2])}")
        if self.movie.actors:
            info_parts.append(f"主演: {' / '.join(self.movie.actors[:3])}")
        info_label = QLabel(" | ".join(info_parts))
        info_label.setStyleSheet("color: #555;")
        info_label.setWordWrap(True)
        right.addWidget(info_label)

        # 简介
        summary = self.movie.summary or ""
        if summary:
            if len(summary) > 120:
                summary = summary[:120] + "…"
            summary_label = QLabel(summary)
            summary_label.setStyleSheet("color: #777;")
            summary_label.setWordWrap(True)
            summary_label.setMaximumHeight(48)
            right.addWidget(summary_label)

        right.addStretch(1)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.open_btn = QPushButton("打开豆瓣")
        self.open_btn.setFixedWidth(90)
        self.open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(self.movie.douban_url))
        )
        btn_row.addWidget(self.open_btn)

        self.search_btn = QPushButton("搜磁力")
        self.search_btn.setFixedWidth(90)
        self.search_btn.setStyleSheet(
            "background-color: #1976d2; color: white; font-weight: bold;"
        )
        self.search_btn.clicked.connect(self._emit_search)
        btn_row.addWidget(self.search_btn)

        right.addLayout(btn_row)

        root.addLayout(right, 1)

    def _emit_search(self) -> None:
        query = self.movie.search_query()
        if query:
            self.search_requested.emit(query)

    @Slot(str, QPixmap)
    def _on_cover_loaded(self, douban_id: str, pixmap: QPixmap) -> None:
        if douban_id != self.movie.douban_id:
            return
        scaled = pixmap.scaled(
            self.COVER_W, self.COVER_H,
            Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation,
        )
        self.cover_label.setPixmap(scaled)
        self.cover_label.setStyleSheet("border: 1px solid #ddd;")


# ---------- 豆瓣发现 Tab ----------

class DoubanTab(QWidget):
    """豆瓣发现页：顶部搜索框 + 榜单切换 + 卡片列表。

    search_requested(title) 信号：主窗口接收到后，切到磁力 Tab 并填入搜索词。
    """
    search_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        os.makedirs(COVER_CACHE_DIR, exist_ok=True)
        self._covers = CoverLoader()
        self._load_requested = False
        self._thread: Optional[QThread] = None
        self._worker: Optional[DoubanLoadWorker] = None
        self._build_ui()   # 先建 UI，Top250 加载延迟到 show 后

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._load_requested:
            self._load_requested = True
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._load_top250)

    def _build_ui(self) -> None:
        from PySide6.QtWidgets import QHBoxLayout

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # 顶部工具栏
        bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入片名搜索豆瓣…")
        self.search_input.returnPressed.connect(self._do_search)
        bar.addWidget(self.search_input, 1)

        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self._do_search)
        bar.addWidget(self.search_btn)

        self.top250_btn = QPushButton("豆瓣 Top 250")
        self.top250_btn.clicked.connect(self._load_top250)
        bar.addWidget(self.top250_btn)

        root.addLayout(bar)

        # 状态 / 进度
        self.status_label = QLabel("加载中…")
        self.status_label.setStyleSheet("color: #666;")
        root.addWidget(self.status_label)

        # 滚动区 + 卡片容器
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_widget)
        root.addWidget(self.scroll, 1)

    # ---------- 加载入口 ----------

    def _clear_list(self) -> None:
        while self.list_layout.count() > 1:   # 保留末尾 stretch
            item = self.list_layout.takeAt(0)
            if w := item.widget():
                w.deleteLater()

    def _load_top250(self) -> None:
        self.status_label.setText("正在加载豆瓣 Top 250…")
        self._start_worker("top250")

    def _do_search(self) -> None:
        q = self.search_input.text().strip()
        if not q:
            return
        self.status_label.setText(f"豆瓣搜索: {q} …")
        self._start_worker("search", query=q)

    def _start_worker(self, action: str, query: str = "") -> None:
        # 停止之前的
        if self._thread:
            self._thread.quit()
            self._thread.wait(2000)

        self._thread = QThread(self)
        self._worker = DoubanLoadWorker(action, query)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    @Slot(list, str)
    def _on_worker_finished(self, items: list, error: str) -> None:
        if error:
            self.status_label.setText(f"加载失败: {error}")
            return
        self._clear_list()
        if not items:
            self.status_label.setText("没有找到匹配的电影")
            return
        self.status_label.setText(f"共 {len(items)} 部电影")
        for movie in items:
            card = MovieCard(movie, self._covers)
            card.search_requested.connect(self.search_requested.emit)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)
