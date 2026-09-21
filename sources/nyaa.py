"""Nyaa.si 搜索源。

Nyaa 是亚洲动漫/影视资源聚合站，返回干净的 HTML 表格：
  cell0: 分类链接 (/?c=X_Y)
  cell1: 标题 + 详情页 /view/NNNNNN
  cell2: magnet:?xt=urn:btih:... 链接
  cell3: 大小（如 17.5 GiB）
  cell4: 发布日期
  cell5: 做种数
  cell6: 吸血数
  cell7: 完成数

URL: https://nyaa.si/?f=0&c=0_0&q=QUERY
mode=tv 时 c=0_0 保持全分类；mode=movie 时同样保持（Nyaa 内容以番剧为主，不过也有电影）。
"""
from __future__ import annotations

import re
from typing import List, Tuple
from urllib.parse import quote

from .base import SearchSource
from config import AppConfig
from core.http_client import HttpClient
from core.models import Resolution, TorrentResult


BASE_URL = "https://nyaa.si/"


def _parse_size(text: str) -> int:
    """Nyaa 大小文本（如 '17.5 GiB' / '5.0 GiB' / '850.3 MiB'）→ 字节数。"""
    text = text.strip().lower()
    m = re.match(r"([\d.]+)\s*([kmgtp]?i?b)", text)
    if not m:
        return 0
    val = float(m.group(1))
    unit = m.group(2)
    mult = {
        "b": 1, "ib": 1,
        "kb": 1024 ** 1, "kib": 1024 ** 1,
        "mb": 1024 ** 2, "mib": 1024 ** 2,
        "gb": 1024 ** 3, "gib": 1024 ** 3,
        "tb": 1024 ** 4, "tib": 1024 ** 4,
    }.get(unit, 1)
    return int(val * mult)


def _parse_title_from_html(cell_html: str) -> str:
    """Nyaa cell1 里可能有 badge 等，提取纯文本标题。"""
    # 去掉 <img> 标签（badge 图标）
    clean = re.sub(r'<img[^>]*>', '', cell_html)
    # 去掉 <a> 标签的 href 只留文字
    clean = re.sub(r'<a[^>]*>(.*?)</a>', r'\1', clean, flags=re.DOTALL)
    # 去掉 span / small / label 等标签
    clean = re.sub(r'<[^>]+>', ' ', clean)
    # HTML 实体解码
    from html import unescape
    clean = unescape(clean)
    # 合并多余空白
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def _extract_links(cell_html: str) -> Tuple[str, str]:
    """从 cell2 提取 detail_url（.torrent 或 /view/N 都行）和 magnet。"""
    links = re.findall(r'href="([^"]+)"', cell_html)
    detail = ""
    magnet = ""
    for l in links:
        if l.startswith("magnet:"):
            magnet = l.replace("&amp;", "&")
        elif l.endswith(".torrent") or "/view/" in l:
            if not detail:
                detail = l
    if detail and detail.startswith("/"):
        detail = BASE_URL + detail.lstrip("/")
    return detail, magnet


class NyaaSource(SearchSource):
    name = "Nyaa.si"
    enabled = True

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.http = HttpClient(proxy=config.proxy, timeout=10, max_retries=1)

    def search(self, query: str, mode: str = "movie") -> List[TorrentResult]:
        # c=0_0 全分类，c=3_0 是 Anime - English-translated
        url = f"{BASE_URL}?f=0&c=0_0&q={quote(query)}&p=1"
        try:
            body = self.http.get(url)
        except Exception:
            return []
        if not body:
            return []

        results: List[TorrentResult] = []

        # 找表格
        m = re.search(r'<table[^>]*class="table[^"]*"[^>]*>(.*?)</table>', body, re.DOTALL | re.IGNORECASE)
        if not m:
            return []
        table = m.group(1)

        # 逐行解析
        for row_html in re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.DOTALL | re.IGNORECASE):
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL | re.IGNORECASE)
            if len(cells) < 6:
                continue
            # cell2 必须有 magnet
            _detail, magnet = _extract_links(cells[2])
            if not magnet:
                continue

            title = _parse_title_from_html(cells[1])
            if not title:
                continue

            magnet_clean = magnet
            m_hash = re.search(r"btih:([a-fA-F0-9]{40})", magnet_clean, re.I)
            info_hash = m_hash.group(1).lower() if m_hash else ""

            size_bytes = _parse_size(re.sub(r'<[^>]+>', '', cells[3]))
            seeders_text = re.sub(r'<[^>]+>', '', cells[5]).strip()
            seeders = int(seeders_text) if seeders_text.isdigit() else 0
            leechers_text = re.sub(r'<[^>]+>', '', cells[6]).strip() if len(cells) > 6 else "0"
            leechers = int(leechers_text) if leechers_text.isdigit() else 0

            # 分辨率：从标题里猜
            res = Resolution.UNKNOWN
            for r in ("2160p", "4k", "1080p", "720p", "480p", "bluray", "dvdrip", "webrip", "webdl"):
                if r in title.lower():
                    try:
                        res = Resolution(r)
                    except ValueError:
                        pass
                    break

            results.append(TorrentResult(
                title=title,
                magnet_link=magnet_clean,
                info_hash=info_hash,
                source="Nyaa.si",
                resolution=res,
                size_bytes=size_bytes,
                size_display=re.sub(r'<[^>]+>', '', cells[3]).strip(),
                seeders=seeders,
                leechers=leechers,
                detail_url=_detail,
                upload_date=None,
            ))

        return results
