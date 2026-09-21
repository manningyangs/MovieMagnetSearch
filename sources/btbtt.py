"""BT之家搜索源：Discuz 论坛（www.1lou.me），两步取磁链。"""
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
from utils.magnet import build_magnet, extract_info_hash, format_size
from utils.resolution import detect_resolution

BASE_URL = "https://www.1lou.me"

# 帖子详情页链接：thread-{tid}-1-1.html
THREAD_LINK_RE = re.compile(r"thread-(\d+)-\d+-\d+\.html")
# 磁力链接正则
MAGNET_RE = re.compile(r"magnet:\?xt=urn:btih:([A-Fa-f0-9]{40})", re.IGNORECASE)
# 文件大小（如 1.5GB / 2.3 GB / 850MB）
SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[GM]B", re.IGNORECASE)
# 日期（如 2024-1-15 或 2024-1-15 14:30）
DATE_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?")


class BtbttSource(SearchSource):
    name = "BT之家"
    enabled = True
    lang = "zh"  # 中文站，用中文片名搜索

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.http = HttpClient(proxy=config.proxy, timeout=15, max_retries=1)

    def search(self, query: str, mode: str = "movie") -> List[TorrentResult]:
        results: List[TorrentResult] = []
        # 搜索页
        search_url = f"{BASE_URL}/search.php?mod=forum&searchsubmit=yes&srchtxt={query}"
        html = self._get_html(search_url)
        if not html:
            return results
        # 提取帖子链接（去重保留顺序）
        tids = []
        seen = set()
        for m in THREAD_LINK_RE.finditer(html):
            tid = m.group(1)
            if tid not in seen:
                seen.add(tid)
                tids.append(tid)
        # 限制数量，避免过多请求
        for tid in tids[:15]:
            try:
                item = self._parse_thread(tid, query)
            except Exception:
                item = None
            if item:
                results.append(item)
        return results

    def _get_html(self, url: str) -> Optional[str]:
        try:
            return self.http.get(url, headers={"Referer": BASE_URL})
        except Exception:
            return None

    def _parse_thread(self, tid: str, query: str) -> Optional[TorrentResult]:
        thread_url = f"{BASE_URL}/thread-{tid}-1-1.html"
        html = self._get_html(thread_url)
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")

        # 标题
        title_el = soup.select_one("#thread_subject, .ts a, h1")
        title = title_el.get_text(strip=True) if title_el else f"BT之家 {tid}"
        # 磁力链接（页面中第一个）
        m_match = MAGNET_RE.search(html)
        if not m_match:
            return None
        info_hash = m_match.group(1).lower()
        magnet = m_match.group(0)
        # 大小：从正文找
        size_bytes = 0
        size_match = SIZE_RE.search(html)
        if size_match:
            val = float(size_match.group(1))
            unit = size_match.group(0).upper()
            if "GB" in unit:
                size_bytes = int(val * 1024 ** 3)
            elif "MB" in unit:
                size_bytes = int(val * 1024 ** 2)
        # 发布日期
        upload_date = None
        d_match = DATE_RE.search(html)
        if d_match:
            try:
                y, mo, da, hh, mm = d_match.groups()
                if hh and mm:
                    upload_date = datetime(int(y), int(mo), int(da), int(hh), int(mm), tzinfo=timezone.utc)
                else:
                    upload_date = datetime(int(y), int(mo), int(da), tzinfo=timezone.utc)
            except (ValueError, TypeError):
                upload_date = None

        resolution = detect_resolution(title)
        return TorrentResult(
            title=title,
            magnet_link=magnet if magnet.startswith("magnet:?xt=urn:btih:") else build_magnet(info_hash, title),
            info_hash=info_hash,
            size_bytes=size_bytes,
            size_display=format_size(size_bytes) if size_bytes else "未知",
            seeders=0,  # BT之家无做种数字段
            leechers=0,
            upload_date=upload_date,
            source=self.name,
            resolution=resolution,
            detail_url=thread_url,
        )
