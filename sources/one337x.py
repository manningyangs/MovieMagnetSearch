"""1337x 搜索源：需 curl_cffi 绕 Cloudflare，搜索页→详情页两步取磁链。"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import AppConfig
from core.http_client import HttpClient
from core.models import Resolution, TorrentResult
from sources.base import SearchSource
from utils.magnet import format_size
from utils.resolution import detect_resolution

BASE_URL = "https://www.1337x.to"
SEARCH_URL = BASE_URL + "/category-search/{query}/Movies/1/"
MAGNET_RE = re.compile(r"magnet:\?xt=urn:btih:([A-Fa-f0-9]{40})", re.IGNORECASE)
# 1337x 的相对时间格式多样，尽量解析
DATE_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):?\d{0,2}"
)


class One337xSource(SearchSource):
    name = "1337x"
    enabled = True

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.http = HttpClient(proxy=config.proxy, timeout=10, max_retries=1)

    def search(self, query: str, mode: str = "movie") -> List[TorrentResult]:
        results: List[TorrentResult] = []
        url = SEARCH_URL.format(query=query.replace(" ", "+"))
        html = self._get(url)
        if not html:
            return results
        soup = BeautifulSoup(html, "lxml")
        rows = soup.select("tbody tr")
        for tr in rows[:30]:
            try:
                item = self._parse_row(tr)
            except Exception:
                item = None
            if item:
                results.append(item)
        return results

    def _get(self, url: str) -> Optional[str]:
        try:
            return self.http.get(url, use_browser_tls=True)
        except Exception:
            return None

    def _parse_row(self, tr) -> Optional[TorrentResult]:
        # 标题与详情页链接：第二/第一个 <a>
        a = tr.select_one("td.name a:nth-of-type(2)") or tr.select_one("td.name a")
        if not a:
            return None
        title = a.get_text(strip=True)
        detail_url = urljoin(BASE_URL, a.get("href", ""))
        if not detail_url:
            return None

        # 大小、做种、下载（class 命名）
        size_text = self._cell(tr, ".size")
        seeds = self._int_cell(tr, ".seeds")
        leeches = self._int_cell(tr, ".leeches")
        date_text = self._cell(tr, ".coll-2, td.coll-2")

        size_bytes = self._parse_size(size_text)
        upload_date = self._parse_date(date_text)

        # 详情页取磁链
        magnet, info_hash = self._fetch_magnet(detail_url)
        if not magnet or not info_hash:
            return None

        resolution = detect_resolution(title)
        return TorrentResult(
            title=title,
            magnet_link=magnet,
            info_hash=info_hash,
            size_bytes=size_bytes,
            size_display=size_text or format_size(size_bytes),
            seeders=seeds,
            leechers=leeches,
            upload_date=upload_date,
            source=self.name,
            resolution=resolution,
            detail_url=detail_url,
        )

    def _cell(self, tr, selector: str) -> str:
        el = tr.select_one(selector)
        return el.get_text(strip=True) if el else ""

    def _int_cell(self, tr, selector: str) -> int:
        txt = self._cell(tr, selector)
        m = re.search(r"\d+", txt)
        return int(m.group()) if m else 0

    def _parse_size(self, text: str) -> int:
        if not text:
            return 0
        m = re.search(r"(\d+(?:\.\d+)?)\s*([KMGT]B)", text, re.IGNORECASE)
        if not m:
            return 0
        val = float(m.group(1))
        unit = m.group(2).upper()
        mult = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}.get(unit, 0)
        return int(val * mult)

    def _parse_date(self, text: str) -> Optional[datetime]:
        if not text:
            return None
        m = DATE_RE.search(text)
        if not m:
            return None
        try:
            return datetime(*[int(x) for x in m.groups()], tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

    def _fetch_magnet(self, detail_url: str):
        html = self._get(detail_url)
        if not html:
            return None, None
        m = MAGNET_RE.search(html)
        if not m:
            return None, None
        magnet = m.group(0)
        info_hash = m.group(1).lower()
        # 详情页可能有完整磁链（含 trackers），优先用页面里的
        return magnet, info_hash
