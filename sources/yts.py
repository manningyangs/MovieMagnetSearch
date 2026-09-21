"""YTS 搜索源：官方 API，自动切换可用镜像（yts.ag / yts.lt / yts.mx）。

yts.mx 在某些代理环境下被封（SSL EOF），做了多域 fallback。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from config import AppConfig
from core.http_client import HttpClient
from core.models import Resolution, TorrentResult
from sources.base import SearchSource
from utils.magnet import build_magnet, format_size
from utils.resolution import detect_resolution

YTS_API_PATHS = [
    "https://yts.ag/api/v2/list_movies.json",
    "https://yts.lt/api/v2/list_movies.json",
    "https://yts.mx/api/v2/list_movies.json",
]


class YtsSource(SearchSource):
    name = "YTS"
    enabled = True

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        # 用 base_url 自己拼完整 URL，因为需要尝试多个域
        self.http = HttpClient(proxy=config.proxy, timeout=10, max_retries=1)

    def search(self, query: str, mode: str = "movie") -> List[TorrentResult]:
        if mode != "movie":
            return []  # YTS 只提供电影
        params = {"query_term": query, "limit": 50}
        data = None
        for api_url in YTS_API_PATHS:
            try:
                data = self.http.get_json(api_url, params=params)
                if data and data.get("status") == "ok":
                    break
            except Exception:
                continue
        if not data or data.get("status") != "ok":
            return []
        movies = (data.get("data") or {}).get("movies") or []
        results: List[TorrentResult] = []
        for m in movies:
            title_long = m.get("title_long") or m.get("title") or query
            for t in m.get("torrents") or []:
                info_hash = (t.get("hash") or "").strip()
                if not info_hash:
                    continue
                size_bytes = int(t.get("size_bytes") or 0)
                quality = t.get("quality") or ""
                display_title = f"{title_long} [{quality}]"
                resolution = detect_resolution(display_title)
                if resolution == Resolution.UNKNOWN and quality:
                    resolution = detect_resolution(quality) or Resolution.UNKNOWN
                date_unix = t.get("date_uploaded_unix")
                upload_date = None
                if date_unix:
                    upload_date = datetime.fromtimestamp(int(date_unix), tz=timezone.utc)
                magnet = build_magnet(info_hash, display_title)
                results.append(
                    TorrentResult(
                        title=display_title,
                        magnet_link=magnet,
                        info_hash=info_hash.lower(),
                        size_bytes=size_bytes,
                        size_display=format_size(size_bytes) if size_bytes else (t.get("size") or "未知"),
                        seeders=int(t.get("seeds") or 0),
                        leechers=int(t.get("peers") or 0),
                        upload_date=upload_date,
                        source=self.name,
                        resolution=resolution,
                        detail_url=f"https://yts.mx/movies/{m.get('slug', '')}",
                    )
                )
        return results
