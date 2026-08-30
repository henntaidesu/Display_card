# -*- coding: utf-8 -*-
"""图床连接配置。存 app_settings 表，在网页「系统配置」里改，改完立即生效。"""

from __future__ import annotations

from typing import Any, Dict

from src import settings_store

# app_settings 里的键前缀，避免和别的配置撞名
_PREFIX = "image_hosting_"

KEYS = {
    "base_url": _PREFIX + "base_url",
    "public_base": _PREFIX + "public_base",
    "project": _PREFIX + "project",
    "token": _PREFIX + "token",
    "timeout": _PREFIX + "timeout",
    "verify_tls": _PREFIX + "verify_tls",
}

DEFAULTS = {
    "base_url": "http://127.0.0.1:9990",
    "public_base": "",
    "project": "displaycard",
    "token": "",
    "timeout": "30",
    "verify_tls": "1",
}


def _clean_base(url: str) -> str:
    """去掉尾部斜杠。带斜杠时拼出来会变成 ``//api/v1/...``，有些反代会 404。"""
    return (url or "").strip().rstrip("/")


def get() -> Dict[str, Any]:
    raw = settings_store.get_many(KEYS.values())
    values = {name: (raw.get(key) if raw.get(key) is not None else DEFAULTS[name])
              for name, key in KEYS.items()}
    try:
        timeout = max(5, int(str(values["timeout"]).strip() or "30"))
    except (TypeError, ValueError):
        timeout = 30
    return {
        "base_url": _clean_base(values["base_url"]),
        # 后端常从内网直连图床，浏览器却要走对外域名——两者不是一个地址。
        # 没单独填时退回 base_url，本机自用的场景下这就是对的。
        "public_base": _clean_base(values["public_base"]) or _clean_base(values["base_url"]),
        "project": (values["project"] or "").strip(),
        "token": (values["token"] or "").strip(),
        "timeout": timeout,
        "verify_tls": str(values["verify_tls"]).strip() not in ("0", "false", "False", ""),
    }


def save(payload: Dict[str, Any]) -> None:
    """保存配置。``token`` 传空字符串表示「不修改已保存的 Token」——

    前端永远拿不到已存的 Token（get_public 不回传），如果空值当成「清空」，
    用户每次只改地址、Token 框留空，就会把 Token 悄悄抹掉。
    """
    for name, key in KEYS.items():
        if name not in payload:
            continue
        value = payload[name]
        if name == "token" and not str(value or "").strip():
            continue
        if name == "verify_tls":
            settings_store.set(key, "1" if value else "0")
        else:
            settings_store.set(key, str(value if value is not None else "").strip())


def get_public() -> Dict[str, Any]:
    """给前端看的配置。**Token 只回一个是否已设置的布尔值，本体永不出后端。**"""
    cfg = get()
    return {
        "base_url": cfg["base_url"],
        "public_base": cfg["public_base"],
        "project": cfg["project"],
        "timeout": cfg["timeout"],
        "verify_tls": cfg["verify_tls"],
        "token_set": bool(cfg["token"]),
        "configured": bool(cfg["base_url"] and cfg["project"] and cfg["token"]),
    }
