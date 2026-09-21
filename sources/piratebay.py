"""The Pirate Bay 搜索源：apibay.org JSON API，单步，info_hash 拼磁链。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from config import AppConfig
from core.http_client import HttpClient
from core.models import Resolution, TorrentResult
from sources.base import SearchSource
from utils.magnet import build_magnet, format_size
from utils.resolution import detect_resolution

API_URL = "https://apibay.org/q.php"
CAT_MOVIE = "200"  # 电影分类
CAT_TV = "205"     # TV Shows（含剧集/综艺）


class PirateBaySource(SearchSource):
    name = "The Pirate Bay"
    enabled = True

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.http = HttpClient(proxy=config.proxy, timeout=15, max_retries=1)

    def search(self, query: str, mode: str = "movie") -> List[TorrentResult]:
        cat = CAT_TV if mode == "tv" else CAT_MOVIE
        params = {"q": query, "cat": cat}
        data = self.http.get_json(API_URL, params=params)
        if not isinstance(data, list):
            return []
        results: List[TorrentResult] = []
        for item in data:
            info_hash = (item.get("info_hash") or "").strip()
            if not info_hash:
                continue
            name = item.get("name") or "Pirate Bay torrent"
            size_bytes = int(item.get("size") or 0)
            added = item.get("added")
            upload_date = None
            if added:
                try:
                    upload_date = datetime.fromtimestamp(int(added), tz=timezone.utc)
                except (ValueError, TypeError):
                    upload_date = None
            magnet = build_magnet(info_hash, name)
            results.append(
                TorrentResult(
                    title=name,
                    magnet_link=magnet,
                    info_hash=info_hash.lower(),
                    size_bytes=size_bytes,
                    size_display=format_size(size_bytes),
                    seeders=int(item.get("seeders") or 0),
                    leechers=int(item.get("leechers") or 0),
                    upload_date=upload_date,
                    source=self.name,
                    resolution=detect_resolution(name),
                    detail_url=f"https://thepiratebay.org/description.php?id={item.get('id', '')}",
                )
            )
        return results
