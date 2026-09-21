"""数据模型：分辨率枚举与种子结果。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Resolution(str, Enum):
    FOUR_K = "4K"
    FHD = "1080p"
    HD = "720p"
    SD = "SD"
    UNKNOWN = "未知"

    @property
    def score(self) -> int:
        """分辨率固定分值，用于评分。"""
        return {
            Resolution.FOUR_K: 100,
            Resolution.FHD: 80,
            Resolution.HD: 60,
            Resolution.SD: 40,
            Resolution.UNKNOWN: 50,
        }[self]


@dataclass
class TorrentResult:
    title: str
    magnet_link: str
    info_hash: str
    size_bytes: int
    size_display: str
    seeders: int
    leechers: int
    upload_date: Optional[datetime]
    source: str
    resolution: Resolution
    detail_url: str
    score: float = 0.0
