"""结果相关性过滤：剔除标题与查询无关的默认/热门结果。

解决 The Pirate Bay 在中文查询无匹配时返回无关默认列表的误导问题：
若结果标题不含查询的任何有效 token，则判定无关并剔除。
"""
from __future__ import annotations

import re
from typing import List

from core.models import TorrentResult

# CJK 连续段（中日韩统一表意 + 假名 + 谚文）
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]+")
# 拉丁/数字 token（>=2 字符）
_LATIN_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
# 英文停用词，过滤以免 "the/a/of" 等匹配过宽
_EN_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for",
    "is", "it", "at", "by", "with", "from", "as", "be", "this", "that",
}


def _tokens(query: str) -> List[str]:
    """提取查询的有效 token：CJK 整段 + CJK 单字 + 拉丁词（去停用词）。"""
    if not query:
        return []
    q = query.lower()
    toks: List[str] = []
    for m in _CJK_RE.finditer(q):
        s = m.group(0)
        toks.append(s)
        for ch in s:  # 单字提升中文-中文匹配宽容度
            toks.append(ch)
    for w in _LATIN_TOKEN_RE.findall(q):
        if w in _EN_STOPWORDS:
            continue
        toks.append(w)
    # 去重保序
    seen = set()
    out = []
    for t in toks:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def is_relevant(title: str, query: str) -> None:
    """标题是否与查询相关：至少一个 token 出现在标题中。

    无 token（如纯符号查询）或无标题时判定保留，避免误删。
    """
    if not query or not title:
        return True
    toks = _tokens(query)
    if not toks:
        return True
    t = title.lower()
    return any(tok in t for tok in toks)


def filter_relevant(results: List[TorrentResult], query: str) -> List[TorrentResult]:
    """剔除与查询无关的结果。query 为空时不过滤。"""
    if not query:
        return results
    return [r for r in results if is_relevant(r.title, query)]
