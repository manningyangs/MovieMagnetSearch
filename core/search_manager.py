"""搜索编排：多源并发搜索（ThreadPoolExecutor + QTimer 轮询）、聚合、去重、评分、排序。

采用线程池 + 主线程轮询，所有 Qt 信号都在主线程发射，
规避 QRunnable 跨线程信号 "source has been deleted" 问题。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, Future
import re
from typing import Dict, List, Tuple

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from config import AppConfig
from core.models import TorrentResult
from core.scorer import score_results
from sources.base import SearchSource
from utils.relevance import filter_relevant

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")


def _has_cjk(text: str) -> bool:
    """查询是否含中日韩字符。"""
    return bool(_CJK_RE.search(text or ""))


def _build_sources(config: AppConfig) -> List[SearchSource]:
    """根据配置构造启用的搜索源列表。延迟导入避免未装依赖时崩溃。"""
    sources: List[SearchSource] = []
    if config.sources.yts:
        try:
            from sources.yts import YtsSource
            sources.append(YtsSource(config))
        except Exception:
            pass
    if config.sources.piratebay:
        try:
            from sources.piratebay import PirateBaySource
            sources.append(PirateBaySource(config))
        except Exception:
            pass
    if config.sources.nyaa:
        try:
            from sources.nyaa import NyaaSource
            sources.append(NyaaSource(config))
        except Exception:
            pass
    if config.sources.one337x:
        try:
            from sources.one337x import One337xSource
            sources.append(One337xSource(config))
        except Exception:
            pass
    if config.sources.btbtt:
        try:
            from sources.btbtt import BtbttSource
            sources.append(BtbttSource(config))
        except Exception:
            pass
    if config.sources.dytt:
        try:
            from sources.dytt import DyttSource
            sources.append(DyttSource(config))
        except Exception:
            pass
    if config.jackett.enabled:
        try:
            from sources.jackett import JackettSource
            sources.append(JackettSource(config))
        except Exception:
            pass
    return sources


def _merge_results(results: List[TorrentResult]) -> List[TorrentResult]:
    """按 info_hash 去重：相同 hash 合并保留 seeders 最大值，来源拼接。"""
    merged: Dict[str, TorrentResult] = {}
    extra: List[TorrentResult] = []
    for r in results:
        key = r.info_hash.lower() if r.info_hash else None
        if not key:
            extra.append(r)
            continue
        if key in merged:
            existing = merged[key]
            if r.seeders > existing.seeders:
                existing.seeders = r.seeders
                existing.leechers = max(existing.leechers, r.leechers)
                existing.size_bytes = max(existing.size_bytes, r.size_bytes)
                if existing.size_display == "未知" and r.size_display != "未知":
                    existing.size_display = r.size_display
            if r.source not in existing.source:
                existing.source = existing.source + ", " + r.source
            if r.upload_date and (
                not existing.upload_date or r.upload_date > existing.upload_date
            ):
                existing.upload_date = r.upload_date
        else:
            merged[key] = r
    return list(merged.values()) + extra


def _run_source(source: SearchSource, query: str, mode: str) -> Tuple[str, List[TorrentResult], str]:
    """在工作线程执行单源搜索，返回 (name, results, error)。不抛异常。

    用该源实际收到的查询词过滤无关默认结果（如 Pirate Bay 中文查询返回的热门列表）。
    """
    try:
        results = source.search(query, mode=mode) or []
        results = filter_relevant(results, query)
        return source.name, results, ""
    except Exception as e:
        return source.name, [], f"{type(e).__name__}: {str(e)[:120]}"


# 从片名中剥离季号/集号后缀，得到翻译用的主体
_STRIP_TV_RE = re.compile(
    r"\s*[-_\.]*\s*(?:s\s*\d{1,3}(?:[\s\-_\.]?e\s*\d{1,4}(?:[\s\-~]+e?\s*\d{1,4})?)?|season\s*\d{1,3}|第\s*[一二三四五六七八九十百零\d]+\s*季|第\s*[一二三四五六七八九十百零\d]+\s*集)",
    re.IGNORECASE,
)


def _strip_season_episode(query: str) -> str:
    """从查询中去掉季号/集号（例如 Season 1 / S01 / 第一季 / 第05集），返回片名主体。"""
    stripped = _STRIP_TV_RE.sub(" ", query).strip()
    # 清理多余分隔符残留
    stripped = re.sub(r"[\.\-_\s]+", " ", stripped).strip()
    return stripped or query


def _effective_query(source: SearchSource, query: str, en_titles: List[str]) -> str:
    """根据源语言偏好与 TMDB 翻译结果，决定传给该源的查询词。

    - 中文站(lang=zh)：始终用原始中文查询
    - 英文站(lang=en)：有翻译时用首个英文名，否则用原始查询
    """
    if source.lang == "zh":
        return query
    if en_titles:
        return en_titles[0]
    return query


class SearchManager(QObject):
    search_started = Signal(int)  # 本次启用的搜索源总数
    source_progress = Signal(int, int)  # 已完成源数, 源总数
    source_finished = Signal(str, int, str)  # name, count, error
    search_finished = Signal(list)
    search_failed = Signal(str)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self._executor: ThreadPoolExecutor = None
        self._futures: List[Future] = []
        self._aggregated: List[TorrentResult] = []
        self._query: str = ""
        self._sources: List[SearchSource] = []
        self._total: int = 0
        self._mode: str = "movie"
        self._timer = QTimer(self)
        self._timer.setInterval(150)  # 轮询间隔
        self._timer.timeout.connect(self._poll)
        self._elapsed = 0
        self.reload_config(config)

    def reload_config(self, config: AppConfig) -> None:
        self.config = config
        self._sources = _build_sources(config)

    def search(self, query: str, mode: str = "movie") -> None:
        if not self._sources:
            self.search_failed.emit("未启用任何搜索源，请到设置中开启。")
            return
        self._query = query
        self._mode = mode
        self._aggregated = []
        self._elapsed = 0
        # 中文片名翻译：维基百科（免费默认）+ TMDB（配 Key 时结果优先），并行执行
        en_titles: List[str] = []
        if _has_cjk(query):
            # 先剥离季/集号，维基才能命中片名主体
            en_titles = self._translate_titles(_strip_season_episode(query))
        # 每源一个线程，传入按语言分流后的有效查询
        self._executor = ThreadPoolExecutor(max_workers=len(self._sources))
        self._futures = []
        for src in self._sources:
            eq = _effective_query(src, query, en_titles)
            self._futures.append(self._executor.submit(_run_source, src, eq, mode))
        self._total = len(self._futures)
        self.search_started.emit(self._total)
        self._timer.start()

    def _translate_titles(self, query: str) -> List[str]:
        """并行查询 TMDB（若配 Key）与维基百科，合并去重，TMDB 优先。"""
        candidates: List[str] = []
        executor = ThreadPoolExecutor(max_workers=2)
        tasks: Dict[str, Future] = {}
        try:
            if self.config.tmdb_api_key:
                def _tmdb() -> List[str]:
                    from core.tmdb import TmdbClient
                    return TmdbClient(
                        self.config.tmdb_api_key, self.config.proxy
                    ).get_titles(query)

                tasks["TMDB"] = executor.submit(_tmdb)

            def _wiki() -> List[str]:
                from core.wikipedia import WikiTitleClient
                return WikiTitleClient(self.config.proxy).get_titles(query)

            tasks["维基百科"] = executor.submit(_wiki)

            for name, f in tasks.items():
                try:
                    titles = f.result(timeout=8)
                except Exception as e:
                    titles = []
                    self.source_finished.emit(
                        name + "翻译", 0,
                        f"{type(e).__name__}: {str(e)[:60]}",
                    )
                if titles:
                    self.source_finished.emit(
                        name + "翻译", 1, "片名: " + " / ".join(titles[:3])
                    )
                else:
                    self.source_finished.emit(name + "翻译", 0, "未找到匹配片名")
                for t in titles:
                    if t not in candidates:
                        candidates.append(t)
        finally:
            executor.shutdown(wait=False)
        return candidates

    @Slot()
    def _poll(self) -> None:
        self._elapsed += self._timer.interval()
        # 收集已完成的 future
        done = [f for f in self._futures if f.done()]
        for f in done:
            try:
                name, results, error = f.result()
            except Exception as e:
                name, results, error = "?", [], str(e)
            self.source_finished.emit(name, len(results), error)
            if results:
                self._aggregated.extend(results)
            self._futures.remove(f)
        done_count = self._total - len(self._futures)
        self.source_progress.emit(done_count, self._total)
        # 全部完成或超时（45s）
        if not self._futures or self._elapsed > 45000:
            self._finish()

    def _finish(self) -> None:
        self._timer.stop()
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
        # 未完成的标记超时
        for f in self._futures:
            if not f.done():
                self.source_finished.emit("?", 0, "超时")
                f.cancel()
        self._futures = []
        merged = _merge_results(self._aggregated)
        scored = score_results(merged, self.config.weights)
        self.source_progress.emit(self._total, self._total)
        self.search_finished.emit(scored)
