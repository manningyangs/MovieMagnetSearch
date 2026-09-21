"""磁力链接工具：info_hash 解析、磁链拼装、默认 tracker 列表。"""
from __future__ import annotations

import re
import urllib.parse
from typing import Optional

# 一组公共 tracker，提升 qBittorrent 发现节点能力
DEFAULT_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.tobysoft.xyz:6969/announce",
    "http://nyaa.tracker.wf:7777/announce",
    "udp://open.stealth.si:6969/announce",
    "udp://tracker.bittor.pw:1337/announce",
    "udp://tracker.moeking.me:6969/announce",
    "wss://tracker.openwebtorrent.com",
]

MAGNET_HASH_RE = re.compile(
    r"magnet:\?xt=urn:btih:([A-Fa-f0-9]{40})", re.IGNORECASE
)


def build_magnet(
    info_hash: str, title: str, trackers: Optional[list] = None
) -> str:
    """用 info_hash + 标题 + tracker 列表拼装标准磁力链接。"""
    info_hash = info_hash.strip().lower()
    parts = [f"xt=urn:btih:{info_hash}"]
    if title:
        parts.append("dn=" + urllib.parse.quote(title, safe=""))
    for tr in trackers or DEFAULT_TRACKERS:
        parts.append("tr=" + urllib.parse.quote(tr, safe=""))
    return "magnet:?" + "&".join(parts)


def extract_info_hash(magnet: str) -> Optional[str]:
    """从磁链中提取 40 位 info_hash；提取失败返回 None。"""
    if not magnet:
        return None
    m = MAGNET_HASH_RE.search(magnet)
    if m:
        return m.group(1).lower()
    # 支持 32 位 base32 hash
    lower = magnet.lower()
    if "xt=urn:btih:" in lower:
        tail = lower.split("xt=urn:btih:", 1)[1]
        h = tail.split("&", 1)[0]
        if len(h) in (32, 40):
            return h
    return None


def format_size(size_bytes: int) -> str:
    """字节数转人类可读字符串。"""
    if size_bytes <= 0:
        return "未知"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit in ("B", "KB"):
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"
