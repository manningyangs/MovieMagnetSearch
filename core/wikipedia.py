"""维基百科片名映射：中文片名 → 英文标题，免费、无需 API Key。

含 CJK 查询时由 SearchManager 调用，作为默认翻译层；
用户另配 TMDB Key 时 TMDB 结果优先，本模块结果补充。
"""
from __future__ import annotations

import re
from typing import List, Optional

from core.http_client import HttpClient

_WIKI_API = "https://zh.wikipedia.org/w/api.php"

# 影视类消歧后缀：The Secret Life of Walter Mitty (2013 film)
_FILM_RE = re.compile(
    r"^(.*?)\s*\((?:(\d{4})\s*)?(?:animated\s+|live-action\s+)?(?:film|movie|anime|television film|TV film)\)\s*$",
    re.IGNORECASE,
)

# 明确非影视的消歧词，命中则丢弃该候选
_NON_MEDIA_HINTS = (
    "musician", "singer", "rapper", "songwriter", "actor", "actress", "song",
    "album", "single", "novel", "novella", "book", "short story", "footballer",
    "basketball", "baseball", "player", "director", "producer", "screenwriter",
    "writer", "tv series", "television series", "web series", "video game",
    "band", "comedian", "presenter", "model", "character",
)


def _clean(en_title: str) -> Optional[str]:
    """清理维基消歧后缀，返回可用于搜索的标题；非影视条目返回 None。"""
    title = en_title.strip()
    m = _FILM_RE.match(title)
    if m:
        return m.group(1).strip()
    if "(" in title:
        inner = title[title.rfind("(") + 1:title.rfind(")")].lower()
        if any(h in inner for h in _NON_MEDIA_HINTS):
            return None
        # 未知消歧（含纯年份）：保守去掉括号
        return title[: title.rfind("(")].strip()
    return title


class WikiTitleClient:
    def __init__(self, proxy: str = "", timeout: int = 6) -> None:
        self.http = HttpClient(proxy=proxy, timeout=timeout, max_retries=0)

    def get_titles(self, query: str) -> List[str]:
        """中文片名 → 英文候选标题，去重保序。失败返回空。"""
        if not query:
            return []
        titles = self._lookup_direct(query)
        if titles:
            return titles
        return self._lookup_search(query)

    def _collect(self, pages: List[dict]) -> List[str]:
        out: List[str] = []
        for page in pages:
            if "missing" in page:
                continue
            for ll in page.get("langlinks", []):
                t = _clean(ll.get("*", ""))
                if t and t not in out:
                    out.append(t)
        return out

    def _lookup_direct(self, query: str) -> List[str]:
        """精确标题 + 重定向查询（含简繁/别名跳转），最可靠。"""
        data = self.http.get_json(
            _WIKI_API,
            params={
                "action": "query",
                "prop": "langlinks",
                "titles": query,
                "lllang": "en",
                "format": "json",
                "redirects": 1,
            },
        )
        if not data:
            return []
        pages = list(data.get("query", {}).get("pages", {}).values())
        return self._collect(pages)

    def _lookup_search(self, query: str) -> List[str]:
        """搜索兜底：处理无重定向的别名，按相关度排序，过滤同名歌曲/人物。"""
        data = self.http.get_json(
            _WIKI_API,
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": 0,
                "gsrlimit": 8,
                "prop": "langlinks",
                "lllang": "en",
                "format": "json",
            },
        )
        if not data:
            return []
        pages = list(data.get("query", {}).get("pages", {}).values())
        pages.sort(key=lambda p: p.get("index", 99))
        return self._collect(pages)
