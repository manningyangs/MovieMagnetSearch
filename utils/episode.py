"""剧集标题解析：从 BT 标题中抽取季/集信息，供 TV 模式分组展示。

返回结构（解析失败返回 None）：
    {
        "season": int | None,          # 季号（Season 1 Complete 也有）
        "episode": int | None,         # 单集号（整季合辑时为 None）
        "is_complete": bool,           # 整季合集 / 全剧合集
        "group_key": str,              # 分组键，例如 "S01E05" / "S01 Complete" / "Complete Series"
    }
"""
from __future__ import annotations

import re
from typing import Optional, Dict

# S01E05 / S1E5 / s01e05
_EPISODE_RE = re.compile(r"[Ss](\d{1,3})[\.\-_]?[Ee](\d{1,4})")
# 1x05 / 1x5
_EPISODE_X_RE = re.compile(r"(?<!\d)(\d{1,2})x(\d{1,3})(?!\d)", re.IGNORECASE)
# S01E01-E12 / S01E01-E12.E13 整季合辑
# 必须显式「跨多集」且末尾有 E 前缀，避免把 E01.720p 误识别
_SEASON_RANGE_RE = re.compile(
    r"[Ss](\d{1,3})[\.\-_]?[Ee](\d{1,3})[\.\-_~]+[Ee](\d{1,3})",
    re.IGNORECASE,
)
# S01 Complete / Season 1 Complete / Season S1 Complete / 第1季全集
_SEASON_COMPLETE_RE = re.compile(
    r"(?:(?:season|s)\s*(\d{1,3})|第\s*(\d{1,3})\s*季).*?(?:complete|全集|整季|全季|all\s*episodes|full\s*season)",
    re.IGNORECASE,
)
# Complete Series（全剧合集，无季号）
_COMPLETE_SERIES_RE = re.compile(r"\bcomplete\s+series\b", re.IGNORECASE)
# 第01集 / EP01 / EP 1 / Episode 1（只有集号、没季号）
_ONLY_EP_RE = re.compile(
    r"(?:(?:ep|episode|ep\.|第\s*集\s*[:：\-_]?)[EePp]?\s*(\d{1,3})(?!\d))",
    re.IGNORECASE,
)
# 中文「第一集 / 第1集」（独立使用）
_CN_EP_RE = re.compile(r"第\s*([一二三四五六七八九十百零\d]+)\s*集")
# 中文季号
_CN_SEASON_RE = re.compile(r"第\s*([一二三四五六七八九十百零\d]+)\s*季")

_CN_NUM_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "零": 0, "百": 100,
}


def _cn_num(s: str) -> Optional[int]:
    """中文数字 → int。支持 1-99、十几十、二十、一百零一、混合写法。"""
    s = s.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    try:
        n = 0
        cur = 0
        for ch in s:
            v = _CN_NUM_MAP.get(ch)
            if v is None:
                return None
            if v >= 10:
                if cur == 0:
                    cur = 1
                n += cur * v
                cur = 0
            else:
                cur = v
        n += cur
        return n if n > 0 else None
    except Exception:
        return None


def parse_episode(title: str) -> Optional[Dict]:
    """从 BT 标题解析剧集信息。返回 dict 或 None。"""
    if not title:
        return None
    t = title.strip()

    # 1. Complete Series（全剧合集，无季号）
    if _COMPLETE_SERIES_RE.search(t):
        return {
            "season": None,
            "episode": None,
            "is_complete": True,
            "group_key": "Complete Series",
        }

    # 2. 整季合辑：Season N Complete / 第N季全集 / S01E01-E12
    m = _SEASON_COMPLETE_RE.search(t)
    if m:
        n = m.group(1) or m.group(2)
        season = _cn_num(n) if n else None
        return {
            "season": season,
            "episode": None,
            "is_complete": True,
            "group_key": f"S{season:02d} Complete" if season else "Season Complete",
        }

    m = _SEASON_RANGE_RE.search(t)
    if m:
        season, start_ep, end_ep = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if end_ep > start_ep:  # 确认是范围（例如 E01-E12），而不是巧合的单集
            return {
                "season": season,
                "episode": None,
                "is_complete": True,
                "group_key": f"S{season:02d} Complete",
            }

    # 3. 标准集号：S01E05 / S1E5 / 1x05
    m = _EPISODE_RE.search(t)
    if m:
        season, ep = int(m.group(1)), int(m.group(2))
        return {
            "season": season,
            "episode": ep,
            "is_complete": False,
            "group_key": f"S{season:02d}E{ep:02d}",
        }

    m = _EPISODE_X_RE.search(t)
    if m:
        season, ep = int(m.group(1)), int(m.group(2))
        return {
            "season": season,
            "episode": ep,
            "is_complete": False,
            "group_key": f"S{season:02d}E{ep:02d}",
        }

    # 4. 中文季号 + 集号的情况：《第2季 第05集》或单独《第05集》
    cn_season = _CN_SEASON_RE.search(t)
    cn_ep = _CN_EP_RE.search(t)
    if cn_season or cn_ep:
        season = _cn_num(cn_season.group(1)) if cn_season else None
        ep = _cn_num(cn_ep.group(1)) if cn_ep else None
        if season is None and ep is None:
            return None
        key = ""
        if season is not None:
            key += f"S{season:02d}"
        if ep is not None:
            key += f"{key}E{ep:02d}" if key else f"E{ep:02d}"
            return {
                "season": season,
                "episode": ep,
                "is_complete": False,
                "group_key": key,
            }
        # 只有季号、没有集号、也没全集关键词 → 不解析（已在 _SEASON_COMPLETE_RE 处理过全集）
        return None

    # 5. EP01 / Episode 1 / 第1集（只有集号，无季号）
    m = _ONLY_EP_RE.search(t)
    if m:
        ep = int(m.group(1))
        return {
            "season": None,
            "episode": ep,
            "is_complete": False,
            "group_key": f"E{ep:02d}",
        }

    return None
