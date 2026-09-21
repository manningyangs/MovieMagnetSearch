"""Jackett 搜索源：本地 Torznab API（默认 9117），聚合已配置的 tracker。"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List
from urllib.parse import quote, urlencode

from config import AppConfig
from core.http_client import HttpClient
from core.models import Resolution, TorrentResult
from sources.base import SearchSource
from utils.magnet import extract_info_hash, format_size
from utils.resolution import detect_resolution


class JackettSource(SearchSource):
    name = "Jackett"
    enabled = True

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.http = HttpClient(proxy=config.proxy, timeout=15, max_retries=1)
        base = config.jackett.url.rstrip("/")
        self.api_key = config.jackett.api_key
        self.search_url = f"{base}/api/v2.0/indexers/all/results/torznab/api"

    def search(self, query: str, mode: str = "movie") -> List[TorrentResult]:
        if not self.api_key:
            return []
        params = {
            "apikey": self.api_key,
            "t": "search",
            "q": query,
            "cat": "2000",  # 电影
            "limit": 100,
            "o": "json",
        }
        url = f"{self.search_url}?{urlencode(params)}"
        data = self.http.get_json(url)
        if not data:
            return []
        items = data.get("channel", {}).get("item", []) if isinstance(data, dict) else []
        # 单条时 item 是 dict 而非 list
        if isinstance(items, dict):
            items = [items]
        results: List[TorrentResult] = []
        for it in items:
            try:
                results.append(self._parse_item(it))
            except Exception:
                continue
        return [r for r in results if r]

    def _parse_item(self, item: dict) -> TorrentResult:
        title = item.get("title") or "Jackett torrent"
        magnet = item.get("link") or ""
        # 部分返回 magnet 在 link，部分在 enclosure
        if not magnet or not magnet.startswith("magnet:"):
            enc = item.get("enclosure") or {}
            if isinstance(enc, dict):
                magnet = enc.get("url") or magnet
        info_hash = extract_info_hash(magnet) or ""
        # 属性（seeders/peers/size/infohash）
        attrs = {a.get("@attributes", {}).get("name") if isinstance(a, dict) else a.get("name"): 
                 (a.get("@attributes", {}).get("value") if isinstance(a, dict) else a.get("value"))
                 for a in (item.get("attr") or [])}
        seeders = self._to_int(attrs.get("seeders"))
        leechers = self._to_int(attrs.get("peers")) - seeders if attrs.get("peers") else 0
        size_bytes = self._to_int(attrs.get("size"))
        pub = item.get("pubDate")
        upload_date = None
        if pub:
            try:
                upload_date = parsedate_to_datetime(pub)
            except (TypeError, ValueError):
                upload_date = None
        return TorrentResult(
            title=title,
            magnet_link=magnet or "",
            info_hash=info_hash,
            size_bytes=size_bytes,
            size_display=format_size(size_bytes),
            seeders=max(0, seeders),
            leechers=max(0, leechers),
            upload_date=upload_date,
            source=self.name,
            resolution=detect_resolution(title),
            detail_url=item.get("comments") or item.get("link") or "",
        )

    @staticmethod
    def _to_int(v) -> int:
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return 0
