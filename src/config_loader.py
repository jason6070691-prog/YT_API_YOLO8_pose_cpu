"""
config_loader.py
讀取 config.yaml，並提供簡單的屬性存取 (dot-access) 包裝。
"""
from __future__ import annotations
import yaml
from pathlib import Path


class ConfigDict(dict):
    """讓 dict 也能用 config.a.b.c 的方式存取，方便閱讀。"""

    def __getattr__(self, key):
        try:
            value = self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc
        if isinstance(value, dict):
            return ConfigDict(value)
        return value

    def __setattr__(self, key, value):
        self[key] = value


def load_config(path: str | Path = "config.yaml") -> ConfigDict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"找不到設定檔: {path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return ConfigDict(raw)
