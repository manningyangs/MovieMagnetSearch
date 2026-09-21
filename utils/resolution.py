"""从种子标题识别分辨率/清晰度。"""
from __future__ import annotations

import re

from core.models import Resolution

# 按精度从高到低匹配，命中即返回
_PATTERNS = [
    (re.compile(r"(2160p|4k|uhd|ultra[\s.-]*hd)", re.IGNORECASE), Resolution.FOUR_K),
    (re.compile(r"(1080p|fhd|full[\s.-]*hd|1920x1080)", re.IGNORECASE), Resolution.FHD),
    (re.compile(r"(720p|hd(?:tv)?|1280x720)", re.IGNORECASE), Resolution.HD),
    (re.compile(r"(480p|360p|240p|dvd|vcd|xvid|rmvb|sd)", re.IGNORECASE), Resolution.SD),
]


def detect_resolution(title: str) -> Resolution:
    """从标题识别分辨率。无法识别返回 UNKNOWN。"""
    if not title:
        return Resolution.UNKNOWN
    for pattern, res in _PATTERNS:
        if pattern.search(title):
            return res
    return Resolution.UNKNOWN
