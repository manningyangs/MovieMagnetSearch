"""TMDB 片名映射：中文/任意片名 → 英文/原名候选，供国际源搜索。

需用户在设置中填入 TMDB API Key（themoviedb.org 免费注册）。
查询含 CJK 时由 SearchManager 调用，把中文片名翻译为英文/原片名。
"""
from __future__ import annotations

from typing import List

from core.http_client import HttpClient

TMDB_SEARCH = "https://api.themoviedb.org/3/search/movie"
TMDB_MOVIE = "https://api.themoviedb.org/3/movie"


class TmdbClient:
    def __init__(self, api_key: str, proxy: str = "", timeout: int = 6) -> None:
        self.api_key = api_key
        self.http = HttpClient(proxy=proxy, timeout=timeout, max_retries=0)

    def get_titles(self, query: str) -> List[str]:
        """返回候选片名列表（原名 + 本地化 + 英文），去重保序。失败返回空。"""
        if not self.api_key or not query:
            return []
        data = self.http.get_json(
            TMDB_SEARCH,
            params={
                "api_key": self.api_key,
                "query": query,
                "language": "zh-CN",
                "page": 1,
                "include_adult": "false",
            },
        )
        if not data:
            return []
        results = data.get("results") or []
        if not results:
            return []
        top = results[0]
        movie_id = top.get("id")
        titles: List[str] = []
        for key in ("original_title", "title"):
            v = (top.get(key) or "").strip()
            if v and v not in titles:
                titles.append(v)
        # 再取英文 locale 的 title/original_title，便于国际源匹配
        if movie_id:
            en = self.http.get_json(
                f"{TMDB_MOVIE}/{movie_id}",
                params={"api_key": self.api_key, "language": "en-US"},
            )
            if en:
                for key in ("title", "original_title"):
                    v = (en.get(key) or "").strip()
                    if v and v not in titles:
                        titles.append(v)
        return titles
