"""豆瓣发现 Tab：Top250 榜单 + 关键词搜索 + 卡片列表 + 剧情简介展开。"""
from __future__ import annotations

import hashlib
import os
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, QSize, QThread, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.douban import DoubanClient, DoubanDetail, DoubanMovie


COVER_CACHE_DIR = os.path.join(
    os.path.expanduser("~"), ".movie_search", "cache", "covers"
)


# ---------- 异步加载 Top250 / 搜索 ----------

class DoubanLoadWorker(QObject):
    """后台线程跑豆瓣榜单/搜索请求。"""
    finished = Signal(list, str)      # (items, error)

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


# ---------- 异步拉详情（含 PoW 绕过）----------

class DoubanDetailWorker(QObject):
    """后台线程拉单部电影详情（PoW 绕过 + 解析）。"""
    finished = Signal(str, object, str)   # (douban_id, DoubanDetail|None, error)

    def __init__(self, douban_id: str) -> None:
        super().__init__()
        self.douban_id = douban_id

    @Slot()
    def run(self) -> None:
        client = DoubanClient()
        try:
            detail = client.get_detail(self.douban_id)
            self.finished.emit(self.douban_id, detail, "")
        except Exception as e:
            self.finished.emit(self.douban_id, None, f"{type(e).__name__}: {e}")


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
    """横向卡片：封面 + 标题 + 评分 + 导演 + 简介 + 展开 + 操作按钮。"""
    search_requested = Signal(str)           # 告诉主窗口去磁力搜索这个标题
    detail_requested = Signal(str)           # 请求加载详情（douban_id）

    COVER_W = 120
    COVER_H = 170

    def __init__(self, movie: DoubanMovie, loader: CoverLoader, parent=None) -> None:
        super().__init__(parent)
        self.movie = movie
        self._loader = loader
        self._expanded = False
        self._detail_loading = False
        self.setMinimumHeight(self.COVER_H + 20)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        self._build_ui()
        # 请求封面
        if movie.douban_id:
            loader.cover_loaded.connect(self._on_cover_loaded)
            loader.load(movie.douban_id, movie.cover_url)

    def _build_ui(self) -> None:
        from PySide6.QtGui import QFont

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        # 封面占位
        self.cover_label = QLabel("封面")
        self.cover_label.setFixedSize(self.COVER_W, self.COVER_H)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet(
            "background-color: #f0f0f0; border: 1px solid #ddd; color: #999;"
        )
        root.addWidget(self.cover_label)

        # 右侧文本区
        right = QVBoxLayout()
        right.setSpacing(3)

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
        self.info_label = QLabel(" | ".join(info_parts))
        self.info_label.setStyleSheet("color: #555;")
        self.info_label.setWordWrap(True)
        right.addWidget(self.info_label)

        # 类型 / 地区 / 片长（详情回来后填）
        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet("color: #666;")
        self.meta_label.setWordWrap(True)
        right.addWidget(self.meta_label)

        # 简介（初始：Top250 tagline；展开后：full_summary）
        initial_summary = self.movie.summary or ""
        if initial_summary:
            if len(initial_summary) > 150:
                initial_summary = initial_summary[:150] + "…"
        self.summary_label = QLabel(initial_summary)
        self.summary_label.setStyleSheet("color: #333;")
        self.summary_label.setWordWrap(True)
        self.summary_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        right.addWidget(self.summary_label)

        # 短评区域（初始隐藏）
        self.comments_label = QLabel("")
        self.comments_label.setStyleSheet("color: #888; border-left: 3px solid #1976d2; padding-left: 8px;")
        self.comments_label.setWordWrap(True)
        self.comments_label.setVisible(False)
        right.addWidget(self.comments_label)

        right.addStretch(1)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.expand_btn = QPushButton("展开剧情")
        self.expand_btn.setFixedWidth(80)
        self.expand_btn.clicked.connect(self._toggle_expand)
        btn_row.addWidget(self.expand_btn)

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

    def _toggle_expand(self) -> None:
        if self._expanded:
            self._collapse()
        elif self._detail_loading:
            pass  # 正在拉
        elif not self.movie.douban_id:
            self.summary_label.setText("（无豆瓣 ID，无法展开）")
        else:
            # 首次展开：发信号让 Tab 异步拉详情
            self._detail_loading = True
            self.expand_btn.setText("加载中…")
            self.expand_btn.setEnabled(False)
            self.detail_requested.emit(self.movie.douban_id)

    @Slot(object)
    def on_detail_loaded(self, detail: Optional[DoubanDetail]) -> None:
        """Tab 收到详情后回来填到卡片。"""
        self._detail_loading = False
        if not detail:
            self.expand_btn.setText("展开剧情")
            self.expand_btn.setEnabled(True)
            self.summary_label.setText("（详情加载失败）")
            return

        # 填 meta：类型 / 地区 / 片长
        meta_parts = []
        if detail.genres:
            meta_parts.append(" / ".join(detail.genres[:4]))
        if detail.countries:
            meta_parts.append(" / ".join(detail.countries))
        if detail.duration:
            meta_parts.append(f"{detail.duration} 分钟")
        self.meta_label.setText("  |  ".join(meta_parts))

        # 标题里补 original_title（如果详情里有、列表里没有）
        if detail.original_title and not self.movie.original_title:
            pass  # 已经在标题行里处理过

        # full_summary 替换掉 tagline
        if detail.full_summary:
            self.summary_label.setText(detail.full_summary)
            self.summary_label.setStyleSheet("color: #222;")

        # 填短评
        if detail.short_comments:
            parts = []
            for cm in detail.short_comments[:3]:
                text = cm.get("content", "")
                if len(text) > 80:
                    text = text[:80] + "…"
                parts.append(f"· {text}")
            self.comments_label.setText("\n".join(parts))
            self.comments_label.setVisible(True)

        self._expand()

    def _expand(self) -> None:
        self._expanded = True
        self.expand_btn.setText("收起")
        self.expand_btn.setEnabled(True)
        self.setMinimumHeight(0)
        self.adjustSize()

    def _collapse(self) -> None:
        self._expanded = False
        self.expand_btn.setText("展开剧情")
        # 简介恢复为 tagline
        summary = self.movie.summary or ""
        if summary:
            if len(summary) > 150:
                summary = summary[:150] + "…"
        self.summary_label.setText(summary)
        self.summary_label.setStyleSheet("color: #333;")
        self.comments_label.setVisible(False)
        self.meta_label.setText("")
        self.setMinimumHeight(self.COVER_H + 20)
        self.adjustSize()

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
    """豆瓣发现页：顶部搜索框 + Top250 / 搜索 + 卡片列表 + 剧情简介展开。"""
    search_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        os.makedirs(COVER_CACHE_DIR, exist_ok=True)
        self._covers = CoverLoader()
        self._load_requested = False
        self._thread: Optional[QThread] = None
        self._worker: Optional[DoubanLoadWorker] = None
        # 详情加载：允许多个并发（每张卡片各自一个线程）
        self._detail_threads: Dict[str, QThread] = {}
        self._detail_workers: Dict[str, DoubanDetailWorker] = {}
        self._cards_by_id: Dict[str, MovieCard] = {}

        self._build_ui()

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

    # ---------- 榜单 / 搜索 ----------

    def _clear_list(self) -> None:
        # 停掉所有详情加载线程
        for tid, th in list(self._detail_threads.items()):
            th.quit()
            th.wait(2000)
        self._detail_threads.clear()
        self._detail_workers.clear()
        self._cards_by_id.clear()
        # 清卡片
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if w := item.widget():
                w.deleteLater()

    def _load_top250(self) -> None:
        self.status_label.setText("正在加载豆瓣 Top 250…")
        self._start_list_worker("top250")

    def _do_search(self) -> None:
        q = self.search_input.text().strip()
        if not q:
            return
        self.status_label.setText(f"豆瓣搜索: {q} …")
        self._start_list_worker("search", query=q)

    def _start_list_worker(self, action: str, query: str = "") -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait(2000)

        self._thread = QThread(self)
        self._worker = DoubanLoadWorker(action, query)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_list_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    @Slot(list, str)
    def _on_list_finished(self, items: list, error: str) -> None:
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
            card.detail_requested.connect(self._on_detail_requested)
            self._cards_by_id[movie.douban_id] = card
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)

    # ---------- 详情加载 ----------

    @Slot(str)
    def _on_detail_requested(self, douban_id: str) -> None:
        if douban_id in self._detail_threads:
            return  # 已经在加载
        th = QThread(self)
        wk = DoubanDetailWorker(douban_id)
        wk.moveToThread(th)
        th.started.connect(wk.run)
        wk.finished.connect(self._on_detail_finished)
        wk.finished.connect(th.quit)
        th.finished.connect(wk.deleteLater)
        self._detail_threads[douban_id] = th
        self._detail_workers[douban_id] = wk
        th.start()

    @Slot(str, object, str)
    def _on_detail_finished(self, douban_id: str, detail, error: str) -> None:
        # 清理线程引用
        self._detail_threads.pop(douban_id, None)
        self._detail_workers.pop(douban_id, None)
        # 找到对应卡片填数据
        card = self._cards_by_id.get(douban_id)
        if card:
            card.on_detail_loaded(detail)
        if error:
            self.status_label.setText(f"详情加载失败: {error}")
