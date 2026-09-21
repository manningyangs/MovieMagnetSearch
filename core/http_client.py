"""统一 HTTP 客户端：UA、代理、重试、curl_cffi/requests 适配。

- use_browser_tls=True 时用 curl_cffi 模拟浏览器 TLS 指纹（绕 Cloudflare）
- 否则用 requests.Session
"""
from __future__ import annotations

import random
import time
from typing import Optional

try:
    import requests
    from requests.adapters import HTTPAdapter
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

try:
    from curl_cffi import requests as cffi_requests
    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False

# 真实浏览器 UA 池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
]


def random_ua() -> str:
    return random.choice(USER_AGENTS)


def _proxy_dict(proxy: str) -> Optional[dict]:
    if not proxy:
        return None
    p = proxy.strip()
    if "://" not in p:
        p = "http://" + p
    return {"http": p, "https": p}


class HttpClient:
    """带重试的 HTTP 客户端。"""

    def __init__(self, proxy: str = "", timeout: int = 15, max_retries: int = 2) -> None:
        self.proxy = proxy
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = None
        if _HAS_REQUESTS:
            self._session = requests.Session()
            self._session.mount("https://", HTTPAdapter(max_retries=1))
            self._session.mount("http://", HTTPAdapter(max_retries=1))

    def get(
        self,
        url: str,
        *,
        use_browser_tls: bool = False,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> Optional[str]:
        """GET 请求，返回响应文本。失败返回 None。"""
        merged = {"User-Agent": random_ua(), "Accept": "*/*", "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
        if headers:
            merged.update(headers)
        proxy = _proxy_dict(self.proxy)

        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                if use_browser_tls:
                    if not _HAS_CURL_CFFI:
                        raise RuntimeError("curl_cffi 未安装，无法绕过 Cloudflare")
                    resp = cffi_requests.get(
                        url,
                        params=params,
                        headers=merged,
                        proxies=proxy,
                        timeout=self.timeout,
                        impersonate="chrome",
                    )
                else:
                    if not _HAS_REQUESTS:
                        raise RuntimeError("requests 未安装")
                    resp = self._session.get(
                        url,
                        params=params,
                        headers=merged,
                        proxies=proxy,
                        timeout=self.timeout,
                    )
                resp.raise_for_status()
                text = resp.text
                # curl_cffi 的 text 属性兼容
                return text
            except Exception as e:
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(0.6 * (attempt + 1))
        # 全部失败
        raise last_err if last_err else RuntimeError("未知请求错误")

    def get_json(
        self,
        url: str,
        *,
        use_browser_tls: bool = False,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
    ):
        """GET 请求并解析 JSON。失败返回 None。"""
        text = self.get(url, use_browser_tls=use_browser_tls, headers=headers, params=params)
        if text is None:
            return None
        import json
        try:
            return json.loads(text)
        except (ValueError, json.JSONDecodeError):
            return None
