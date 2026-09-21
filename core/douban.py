"""豆瓣电影爬虫。

直连 movie.douban.com，不走任何代理（豆瓣是国内站）。
支持 Top 250、关键词搜索、详情页解析、短评拉取。
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_TOP250_HEADERS = {
    "User-Agent": _UA,
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_SEARCH_HEADERS = {
    "User-Agent": _UA,
    "Referer": "https://movie.douban.com/",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
}

_DETAIL_HEADERS = {
    "User-Agent": _UA,
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://movie.douban.com/",
}


@dataclass
class DoubanMovie:
    """豆瓣电影条目（精简字段，用于列表展示）。"""
    douban_id: str = ""
    title: str = ""
    original_title: str = ""        # 英文原名（副标题）
    year: str = ""
    rating: float = 0.0             # 0-10
    rating_count: int = 0
    directors: List[str] = field(default_factory=list)
    actors: List[str] = field(default_factory=list)
    summary: str = ""               # 一句话简介 / tagline
    cover_url: str = ""
    douban_url: str = ""
    rank: int = 0                   # Top250 排名（仅 Top250 有）

    def search_query(self) -> str:
        """生成用于磁力搜索的 query（优先中文 title，让维基翻译链路把中文翻成英文）。"""
        return self.title or self.original_title


@dataclass
class DoubanDetail(DoubanMovie):
    """豆瓣详情页完整字段。"""
    full_summary: str = ""           # 完整剧情简介
    genres: List[str] = field(default_factory=list)
    countries: List[str] = field(default_factory=list)
    duration: str = ""
    short_comments: List[dict] = field(default_factory=list)   # [{user, rating, content}]


class DoubanClient:
    """豆瓣客户端。所有请求不走代理。"""

    def __init__(self, timeout: int = 15) -> None:
        self._session = requests.Session()
        self._session.trust_env = False   # 关键：绕过系统代理（豆瓣国内站）
        self._session.headers.update({"User-Agent": _UA})
        self._timeout = timeout

    # ---------- Top 250 ----------

    def get_top250(self, limit: int = 250, on_page=None) -> List[DoubanMovie]:
        """爬取豆瓣 Top 250 榜单（10 页并行抓取）。

        Args:
            on_page: 可选回调 `(page_idx, items_so_far)`，每页完成就调一次，
                用于 UI 边抓边渲染（增量显示）。
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: List[DoubanMovie] = []
        per_page = 25
        pages = min(10, (limit + per_page - 1) // per_page)

        def _fetch(page_idx: int):
            offset = page_idx * per_page
            url = f"https://movie.douban.com/top250?start={offset}"
            try:
                resp = self._session.get(url, headers=_TOP250_HEADERS, timeout=self._timeout)
                resp.raise_for_status()
                items = self._parse_top250_page(resp.text, start_rank=offset + 1)
                return page_idx, items
            except Exception as e:
                print(f"[Douban] Top250 page {page_idx} failed: {e}")
                return page_idx, []

        # 10 页并发（豆瓣国内站，不走代理，6 并发即可压满）
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(_fetch, p): p for p in range(pages)}
            # 按页序收集，保证排名正确
            page_map: Dict[int, List[DoubanMovie]] = {}
            for f in as_completed(futures):
                page_idx, items = f.result()
                page_map[page_idx] = items
                # 排序后拼出累计结果 + 回调
                results_so_far: List[DoubanMovie] = []
                for p in sorted(page_map.keys()):
                    results_so_far.extend(page_map[p])
                if on_page and callable(on_page):
                    try:
                        on_page(page_idx, list(results_so_far))
                    except Exception:
                        pass

        for p in sorted(page_map.keys()):
            results.extend(page_map[p])
            if len(results) >= limit:
                break
        return results[:limit]

    def _parse_top250_page(self, html_text: str, start_rank: int) -> List[DoubanMovie]:
        soup = BeautifulSoup(html_text, "html.parser")
        out: List[DoubanMovie] = []
        for i, li in enumerate(soup.select("#content .article ol.grid_view > li")):
            rank = start_rank + i
            title_a = li.select_one(".hd > a")
            if not title_a:
                continue
            url = title_a.get("href", "")
            m = re.search(r"/subject/(\d+)/", url)
            douban_id = m.group(1) if m else ""

            # 标题 + 英文副标题
            titles = [t.strip() for t in title_a.stripped_strings]
            title = titles[0] if titles else ""
            original = ""
            if len(titles) > 1:
                # "盗梦空间" + " / Inception" → 后者是 original
                rest = titles[1]
                if rest.startswith("/"):
                    original = rest.lstrip("/").strip()
                else:
                    title = titles[0]
                    original = rest

            # 年份 / 导演 / 演员（在 .bd p 里）
            bd_p = li.select_one(".bd p")
            year = ""
            directors: List[str] = []
            actors: List[str] = []
            if bd_p:
                p_text = bd_p.get_text("\n", strip=True)
                # 导演
                dm = re.search(r"导演[:：]([^\n]+)", p_text)
                if dm:
                    directors = [d.strip() for d in dm.group(1).split("/")[:3]]
                # 年份
                ym = re.search(r"(\d{4})", p_text.split("\n")[-1] if "\n" in p_text else p_text)
                if ym:
                    year = ym.group(1)

            # 评分
            rating = 0.0
            rm = li.select_one(".rating_num")
            if rm and rm.text.strip():
                try:
                    rating = float(rm.text.strip())
                except ValueError:
                    pass

            # 一句话简介
            summary = ""
            q = li.select_one(".quote span")
            if q:
                summary = q.text.strip()

            # 封面
            cover = ""
            img = li.select_one(".pic img")
            if img:
                cover = img.get("src", "") or img.get("data-src", "")

            out.append(DoubanMovie(
                douban_id=douban_id,
                title=title,
                original_title=original,
                year=year,
                rating=rating,
                directors=directors,
                actors=actors,
                summary=summary,
                cover_url=cover,
                douban_url=url,
                rank=rank,
            ))
        return out

    # ---------- 搜索 ----------

    def search(self, query: str, max_results: int = 20) -> List[DoubanMovie]:
        """豆瓣电影搜索，走 subject_suggest JSON 接口。"""
        if not query.strip():
            return []
        url = "https://movie.douban.com/j/subject_suggest"
        try:
            resp = self._session.get(
                url, params={"q": query},
                headers=_SEARCH_HEADERS, timeout=self._timeout,
            )
            resp.raise_for_status()
            raw = resp.json()
        except Exception as e:
            print(f"[Douban] search failed: {e}")
            return []

        results: List[DoubanMovie] = []
        for item in raw[:max_results]:
            if item.get("type") not in ("movie", "tv"):
                continue
            url = item.get("url", "")
            m = re.search(r"/subject/(\d+)/", url)
            douban_id = m.group(1) if m else ""
            results.append(DoubanMovie(
                douban_id=douban_id,
                title=item.get("title", ""),
                original_title=item.get("sub_title", ""),
                year=item.get("year", ""),
                cover_url=item.get("img", ""),
                douban_url=url,
            ))
        return results

    # ---------- 详情 ----------

    def get_detail(self, douban_id: str) -> Optional[DoubanDetail]:
        """根据豆瓣 ID 拉详情页（评分、简介、导演、短评等）。

        豆瓣详情页现在有 SHA-512 PoW 反爬挑战 —— 若 GET 回来的是 PoW 表单，
        就用 Python 重算 nonce 后 POST 到 sec.douban.com/c 走 302 回原页。
        """
        if not douban_id:
            return None
        url = f"https://movie.douban.com/subject/{douban_id}/"

        # 预热：先 GET 电影首页，让豆瓣 session 下发 bid cookie
        try:
            self._session.get(
                "https://movie.douban.com/",
                headers=_DETAIL_HEADERS, timeout=self._timeout,
            )
        except Exception:
            pass

        try:
            resp = self._session.get(url, headers=_DETAIL_HEADERS, timeout=self._timeout)
            resp.raise_for_status()
            html_text = resp.text
        except Exception as e:
            print(f"[Douban] detail failed {douban_id}: {e}")
            return None

        # 检测 PoW 挑战页
        if "载入中" in html_text and 'name="cha"' in html_text:
            html_text = self._solve_pow_and_retry(url, html_text)
            if not html_text:
                return None

        return self._parse_detail_page(html_text, douban_id, url)

    def _solve_pow_and_retry(self, subject_url: str, pow_html: str) -> Optional[str]:
        """从 PoW 表单中提取 cha/tok/red，算 nonce，POST 回 sec.douban.com/c，
        跟进 302 拿到真正的详情页 HTML。"""
        m_tok = re.search(r'name="tok"[^>]*value="([^"]+)"', pow_html)
        m_cha = re.search(r'name="cha"[^>]*value="([^"]+)"', pow_html)
        m_red = re.search(r'name="red"[^>]*value="([^"]+)"', pow_html)
        if not all([m_tok, m_cha, m_red]):
            return None
        tok, cha, red = m_tok.group(1), m_cha.group(1), m_red.group(1)

        # SHA-512 PoW：找最小 nonce 使 hash(cha + nonce) 前 4 个字符为 0
        nonce = 0
        while True:
            nonce += 1
            h = hashlib.sha512((cha + str(nonce)).encode()).hexdigest()
            if h.startswith("0000"):
                break

        try:
            # POST 到 sec.douban.com/c，跟进 302 拿详情页
            resp = self._session.post(
                "https://sec.douban.com/c",
                data={"tok": tok, "cha": cha, "sol": str(nonce), "red": red},
                headers=_DETAIL_HEADERS,
                timeout=self._timeout,
                allow_redirects=True,
            )
            resp.raise_for_status()
            if "v:itemreviewed" in resp.text:
                return resp.text
        except Exception as e:
            print(f"[Douban] PoW POST failed: {e}")

        # 降级：试试直接 POST 到原 subject URL
        try:
            resp = self._session.post(
                subject_url,
                data={"tok": tok, "cha": cha, "sol": str(nonce), "red": red},
                headers={**_DETAIL_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                timeout=self._timeout,
                allow_redirects=True,
            )
            if "v:itemreviewed" in resp.text:
                return resp.text
        except Exception as e:
            print(f"[Douban] PoW fallback POST failed: {e}")
        return None

    def _parse_detail_page(self, html_text: str, douban_id: str, url: str) -> DoubanDetail:
        soup = BeautifulSoup(html_text, "html.parser")
        d = DoubanDetail(douban_id=douban_id, douban_url=url)

        # 标题
        h1 = soup.select_one("#content h1 span[property='v:itemreviewed']")
        if h1:
            d.title = h1.text.strip()
        year_span = soup.select_one("#content h1 .year")
        if year_span:
            ym = re.search(r"(\d{4})", year_span.text)
            if ym:
                d.year = ym.group(1)

        # 评分
        rating_span = soup.select_one(".rating_num[property='v:average']")
        if rating_span:
            try:
                d.rating = float(rating_span.text.strip())
            except ValueError:
                pass
        count_span = soup.select_one("span[property='v:votes']")
        if count_span:
            try:
                d.rating_count = int(count_span.text.strip())
            except ValueError:
                pass

        # 封面
        cover = soup.select_one("#mainpic img")
        if cover:
            d.cover_url = cover.get("src", "")

        # 导演 / 主演 / 类型 / 地区 / 片长
        info_div = soup.select_one("#info")
        if info_div:
            info_html = str(info_div)
            # 导演
            d.directors = [a.text.strip() for a in info_div.select("a[rel='v:directedBy']")]
            # 主演（前5）
            d.actors = [a.text.strip() for a in info_div.select("a[rel='v:starring']")][:5]
            # 类型
            d.genres = [s.text.strip() for s in info_div.select("span[property='v:genre']")]
            # 片长
            dur = info_div.select_one("span[property='v:runtime']")
            if dur:
                d.duration = dur.get("content", "").strip() or dur.text.strip()
            # 地区 / 原名（通过文本解析）
            info_text = info_div.get_text("\n", strip=True)
            cm = re.search(r"制片国家/地区[:：]([^\n]+)", info_text)
            if cm:
                d.countries = [c.strip() for c in cm.group(1).split("/")]
            um = re.search(r"又名[:：]([^\n]+)", info_text)
            if um:
                # 第一个是英文副标题可能被称为又名，保留
                d.original_title = um.group(1).split("/")[0].strip()

        # 完整简介
        summary_div = soup.select_one("span[property='v:summary']") or soup.select_one(".related-info .indent span")
        if summary_div:
            d.full_summary = summary_div.get_text("\n", strip=True)
        if not d.summary and d.full_summary:
            d.summary = d.full_summary[:80] + ("…" if len(d.full_summary) > 80 else "")

        # 短评（前5条）
        d.short_comments = self._parse_short_comments(soup)

        return d

    def _parse_short_comments(self, soup: BeautifulSoup, max_n: int = 5) -> List[dict]:
        out: List[dict] = []
        for c in soup.select(".comment-item")[:max_n]:
            user_a = c.select_one(".comment-info a")
            user = user_a.text.strip() if user_a else ""
            rating = 0.0
            star = c.select_one(".comment-info span[title]")
            if star:
                tm = re.search(r"(\d+)", star.get("class", [""])[-1] or "")
                # 豆瓣 class 'allstar40' → 4 星
                cls = star.get("class", [])
                for cl in cls:
                    m = re.match(r"allstar(\d+)", cl)
                    if m:
                        rating = int(m.group(1)) / 10 * 5
                        break
            content_span = c.select_one(".comment .short") or c.select_one(".comment-content .short")
            content = content_span.text.strip() if content_span else ""
            if content:
                out.append({"user": user, "rating": rating, "content": content})
        return out
