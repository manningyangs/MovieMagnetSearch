"""应用配置管理：Jackett、代理、各源开关、评分权重，持久化到 config.json。"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


def _config_path() -> str:
    """配置文件路径：优先 exe 同级目录，其次脚本目录。"""
    base = getattr(os, "__Compiled__", None)
    if base:
        return os.path.join(os.path.dirname(base), "config.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


@dataclass
class JackettConfig:
    enabled: bool = False
    url: str = "http://127.0.0.1:9117"
    api_key: str = ""


@dataclass
class SourceConfig:
    yts: bool = True
    piratebay: bool = True
    nyaa: bool = True
    one337x: bool = True
    btbtt: bool = True
    dytt: bool = True


@dataclass
class WeightConfig:
    seeders: float = 0.5
    resolution: float = 0.3
    freshness: float = 0.2


@dataclass
class AppConfig:
    jackett: JackettConfig = field(default_factory=JackettConfig)
    proxy: str = ""
    sources: SourceConfig = field(default_factory=SourceConfig)
    weights: WeightConfig = field(default_factory=WeightConfig)
    tmdb_api_key: str = ""  # 可选，用于中文片名翻译为英文搜国际源
    window_width: int = 1200
    window_height: int = 760

    def save(self) -> None:
        path = _config_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    @classmethod
    def load(cls) -> "AppConfig":
        path = _config_path()
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return cls()
        # 逐段合并，缺失字段用默认值
        cfg = cls()
        if "jackett" in data:
            cfg.jackett = JackettConfig(**data["jackett"])
        if "proxy" in data:
            cfg.proxy = data["proxy"]
        if "sources" in data:
            cfg.sources = SourceConfig(**data["sources"])
        if "weights" in data:
            cfg.weights = WeightConfig(**data["weights"])
        if "tmdb_api_key" in data:
            cfg.tmdb_api_key = data["tmdb_api_key"]
        for key in ("window_width", "window_height"):
            if key in data:
                setattr(cfg, key, data[key])
        return cfg
