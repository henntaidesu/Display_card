# -*- coding: utf-8 -*-
"""app_settings 表读写：**除 MySQL 连接以外的所有配置都在这里**。

为什么不用 .env / 配置文件：图床地址、Token、汇率来源这些是用户在网页上改的，
改完下一个请求就要生效。放文件里就要处理「谁来写文件」「打包后文件在哪」「多进程
怎么同步」；放数据库里这些问题都不存在。

值一律以字符串存。取的时候用 get_bool / get_int / get_json 做转换，
存进去什么样、取出来什么样，不做隐式类型推断。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, Optional

from src import db

log = logging.getLogger(__name__)


def get(key: str, default: Optional[str] = None) -> Optional[str]:
    row = db.query_one("SELECT `value` FROM app_settings WHERE `key` = %s", (key,))
    if not row or row.get("value") is None:
        return default
    return row["value"]


def get_many(keys: Iterable[str]) -> Dict[str, Optional[str]]:
    keys = list(keys)
    if not keys:
        return {}
    placeholders = ", ".join(["%s"] * len(keys))
    rows = db.query(
        f"SELECT `key`, `value` FROM app_settings WHERE `key` IN ({placeholders})",
        keys,
    )
    found = {r["key"]: r["value"] for r in rows}
    return {k: found.get(k) for k in keys}


def get_bool(key: str, default: bool = False) -> bool:
    raw = get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def get_int(key: str, default: int = 0) -> int:
    raw = get(key)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        return default


def get_json(key: str, default: Any = None) -> Any:
    raw = get(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        log.warning("配置项 %s 不是合法 JSON，返回默认值", key)
        return default


def set(key: str, value: Any) -> None:  # noqa: A001  与 get 对称，故意占用内置名
    if value is None:
        text = None
    elif isinstance(value, bool):
        text = "1" if value else "0"
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    db.execute(
        "INSERT INTO app_settings (`key`, `value`) VALUES (%s, %s) "
        "ON DUPLICATE KEY UPDATE `value` = VALUES(`value`)",
        (key, text),
    )


def set_many(items: Dict[str, Any]) -> None:
    for key, value in items.items():
        set(key, value)


def delete(key: str) -> None:
    db.execute("DELETE FROM app_settings WHERE `key` = %s", (key,))
