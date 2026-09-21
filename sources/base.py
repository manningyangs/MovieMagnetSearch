"""搜索源抽象基类。各源同步实现 search，在 QThreadPool 工作线程中运行。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from core.models import TorrentResult


class SearchSource(ABC):
    """所有搜索源的基类。失败的源应返回空列表，不应抛出异常中断整体搜索。"""

    name: str = "Base"
    enabled: bool = True
    lang: str = "en"  # "en"=英文站，"zh"=中文站；用于中文片名翻译分流

    @abstractmethod
    def search(self, query: str, mode: str = "movie") -> List[TorrentResult]:
        """按片名搜索，返回种子结果列表。

        mode: "movie"（默认，电影）/ "tv"（剧集/综艺）。
        不支持某类别的源应返回空列表，不应抛异常。
        """
        raise NotImplementedError
