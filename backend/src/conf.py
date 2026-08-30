# -*- coding: utf-8 -*-
"""conf.ini 读取。

**这是全系统唯一的文件配置**，只承载「怎么连上 MySQL」和「监听在哪」。业务配置
（图床连接、汇率来源等）一律存 MySQL 的 app_settings 表，见 settings_store.py。

优先级：环境变量 > conf.ini > 内置默认值。环境变量优先是为了打包后部署——
不用改文件就能换库，也不用把生产密码写进随 exe 分发的 conf.ini 里。
"""

from __future__ import annotations

import configparser
import os
from typing import Any, Dict

from src.app_paths import conf_path

# section -> {key: (环境变量名, 默认值)}
_SPEC: Dict[str, Dict[str, tuple]] = {
    "mysql": {
        "host": ("DISPLAYCARD_MYSQL_HOST", "127.0.0.1"),
        "port": ("DISPLAYCARD_MYSQL_PORT", "3306"),
        "user": ("DISPLAYCARD_MYSQL_USER", "root"),
        "password": ("DISPLAYCARD_MYSQL_PASSWORD", ""),
        "database": ("DISPLAYCARD_MYSQL_DATABASE", "display_card"),
        "charset": ("DISPLAYCARD_MYSQL_CHARSET", "utf8mb4"),
        "pool_size": ("DISPLAYCARD_MYSQL_POOL_SIZE", "4"),
        "pool_recycle": ("DISPLAYCARD_MYSQL_POOL_RECYCLE", "3600"),
    },
    "server": {
        "host": ("DISPLAYCARD_HOST", "0.0.0.0"),
        "port": ("DISPLAYCARD_PORT", "9910"),
    },
}

_cache: Dict[str, Dict[str, str]] | None = None


def _default_conf_text() -> str:
    """按 _SPEC 的默认值拼出一份**不含任何注释**的 conf.ini 文本。

    从 _SPEC 生成而不是写死字符串：以后加/改配置项只动 _SPEC 一处，自动生成的
    conf.ini 跟着变，不会和实际读取的键漂移。
    """
    lines = []
    for section, keys in _SPEC.items():
        lines.append(f"[{section}]")
        for key, (_env, default) in keys.items():
            lines.append(f"{key} = {default}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def ensure_conf_file() -> bool:
    """conf.ini 不存在时写一份不含注释的默认配置；已存在则原样保留。返回是否新建。"""
    path = conf_path()
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_default_conf_text(), encoding="utf-8")
    return True


def _read_file() -> configparser.ConfigParser:
    # inline_comment_prefixes：让 `port = 3306  ; 注释` 这种写法里的注释不被当成值的一部分。
    parser = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    path = conf_path()
    if path.exists():
        # utf-8-sig 而不是 utf-8：编辑器（尤其 VS Code）保存 conf.ini 时常带上 UTF-8 BOM，
        # 纯 utf-8 读会把 BOM 附在第一个 [section] 头上导致整份解析不出任何 section，
        # 后端就静默退回默认值（root/空密码）连不上库。utf-8-sig 有无 BOM 都能正确读。
        parser.read(path, encoding="utf-8-sig")
    return parser


def load(refresh: bool = False) -> Dict[str, Dict[str, str]]:
    global _cache
    if _cache is not None and not refresh:
        return _cache
    parser = _read_file()
    resolved: Dict[str, Dict[str, str]] = {}
    for section, keys in _SPEC.items():
        resolved[section] = {}
        for key, (env_name, default) in keys.items():
            env_value = os.environ.get(env_name)
            if env_value is not None and env_value.strip() != "":
                resolved[section][key] = env_value.strip()
            elif parser.has_option(section, key):
                resolved[section][key] = (parser.get(section, key) or "").strip()
            else:
                resolved[section][key] = default
    _cache = resolved
    return resolved


def _int(value: str, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def mysql_config() -> Dict[str, Any]:
    cfg = load()["mysql"]
    return {
        "host": cfg["host"] or "127.0.0.1",
        "port": _int(cfg["port"], 3306),
        "user": cfg["user"] or "root",
        "password": cfg["password"],
        "database": cfg["database"] or "display_card",
        "charset": cfg["charset"] or "utf8mb4",
        "pool_size": max(1, _int(cfg["pool_size"], 4)),
        "pool_recycle": max(60, _int(cfg["pool_recycle"], 3600)),
    }


def server_config() -> Dict[str, Any]:
    cfg = load()["server"]
    return {"host": cfg["host"] or "0.0.0.0", "port": _int(cfg["port"], 9910)}


def describe() -> Dict[str, Any]:
    """给「系统配置」页看的连接概况。**密码永不回传前端**，只回一个是否已设置的布尔值。"""
    cfg = mysql_config()
    return {
        "conf_path": str(conf_path()),
        "conf_exists": conf_path().exists(),
        "host": cfg["host"],
        "port": cfg["port"],
        "user": cfg["user"],
        "database": cfg["database"],
        "charset": cfg["charset"],
        "password_set": bool(cfg["password"]),
        "pool_size": cfg["pool_size"],
    }
