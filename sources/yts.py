"""YTS 搜索源：官方 API，单步，返回 hash/seeds/peers/size/quality，需拼装磁链。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from config import AppConfig
from core.http_client import HttpClient
from core.models import Resolution, TorrentResult
from sources.base import SearchSource
from utils.magnet import build_magnet, format_size
from utils.resolution import detect_resolution

# 主域对无浏览器 UA 的请求可能被拒，用镜像/主域均可
YTS_API = "https://yts.mx/api/v2/list_movies.json"


class YtsSource(SearchSource):
    name = "YTS"
    enabled = True

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.http = HttpClient(proxy=config.proxy, timeout=15, max_retries=1)

    def search(self, query: str, mode: str = "movie") -> List[TorrentResult]:
        if mode != "movie":
            return []  # YTS 只提供电影
        params = {"query_term": query, "limit": 50}
        data = self.http.get_json(YTS_API, params=params)
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
                # 标题用 电影名 + quality + type 组合，便于识别分辨率
                display_title = f"{title_long} [{quality}]"
                resolution = detect_resolution(display_title)
                if resolution == Resolution.UNKNOWN and quality:
                    # quality 字段本身可能含 1080p/720p/2160p
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
