"""质量评分算法：seeders + resolution + freshness 三维度加权。"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import List

from config import WeightConfig
from core.models import TorrentResult


def _normalize_weights(w: WeightConfig) -> tuple:
    """把三个权重归一化到和为 1。"""
    total = w.seeders + w.resolution + w.freshness
    if total <= 0:
        return (0.5, 0.3, 0.2)
    return (w.seeders / total, w.resolution / total, w.freshness / total)


def _seeders_score(seeders: int, max_seeders: int) -> float:
    """批次内相对归一化（对数缩放）。max_seeders 为本批最大做种数。"""
    if max_seeders <= 0:
        return 0.0
    if seeders <= 0:
        return 0.0
    return 100.0 * math.log(1 + seeders) / math.log(1 + max_seeders)


def _freshness_score(upload_date) -> float:
    """发布时间评分：半年半衰期指数衰减；无日期记 50。"""
    if upload_date is None:
        return 50.0
    now = datetime.now(upload_date.tzinfo) if upload_date.tzinfo else datetime.now()
    delta_days = max(0, (now - upload_date).days)
    # 半衰期 180 天：每过半年分数减半
    return max(0.0, 100.0 * (0.5 ** (delta_days / 180.0)))


def score_results(results: List[TorrentResult], weights: WeightConfig) -> List[TorrentResult]:
    """对结果列表评分并按总分降序排序，返回新列表。"""
    if not results:
        return results

    max_seeders = max((r.seeders for r in results), default=0)
    w_seeds, w_res, w_fresh = _normalize_weights(weights)

    for r in results:
        s_score = _seeders_score(r.seeders, max_seeders)
        r_score = r.resolution.score
        f_score = _freshness_score(r.upload_date)
        total = w_seeds * s_score + w_res * r_score + w_fresh * f_score
        r.score = round(total, 1)

    # 总分降序；同分按 seeders 降序
    results.sort(key=lambda r: (-r.score, -r.seeders))
    return results
