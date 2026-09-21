"""The Pirate Bay 搜索源：apibay.org JSON API，单步，info_hash 拼磁链。

加了 60 秒 LRU 内存缓存（apibay 对同一查询返回 100 条不会频繁变），
减少重复请求。timeout 从 15s 缩到 10s，max_retries 保留 1。
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from config import AppConfig
from core.http_client import HttpClient
from core.models import Resolution, TorrentResult
from sources.base import SearchSource
from utils.magnet import build_magnet, format_size
from utils.resolution import detect_resolution

API_URL = "https://apibay.org/q.php"
CAT_MOVIE = "200"  # 电影分类
CAT_TV = "205"     # TV Shows（含剧集/综艺）

# 60 秒 LRU 内存缓存：(query, cat) → (timestamp, json_list)
_CACHE: Dict[Tuple[str, str], Tuple[float, list]] = {}
_CACHE_TTL = 60


class PirateBaySource(SearchSource):
    name = "The Pirate Bay"
    enabled = True

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.http = HttpClient(proxy=config.proxy, timeout=10, max_retries=1)

    def search(self, query: str, mode: str = "movie") -> List[TorrentResult]:
        cat = CAT_TV if mode == "tv" else CAT_MOVIE
        cache_key = (query, cat)
        now = time.time()

        # 查缓存
        cached = _CACHE.get(cache_key)
        if cached and now - cached[0] < _CACHE_TTL:
            raw_list = cached[1]
        else:
            params = {"q": query, "cat": cat}
            data = self.http.get_json(API_URL, params=params)
            if not isinstance(data, list):
                return []
            raw_list = data
            _CACHE[cache_key] = (now, raw_list)
            # 简单 LRU 清理：超过 200 条就删最旧的一半
            if len(_CACHE) > 200:
                sorted_keys = sorted(_CACHE, key=lambda k: _CACHE[k][0])
                for k in sorted_keys[: len(sorted_keys) // 2]:
                    _CACHE.pop(k, None)

        results: List[TorrentResult] = []
        for item in raw_list:
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
