# -*- coding: utf-8 -*-
"""汇率服务：缓存 → 数据源 → 降级，三层依次尝试。

取一天的汇率会依次做三件事：

1. **查本地缓存**（fx_rates 表）。历史牌价一经公布就永远不变，缓存下来永久有效。
2. 缓存没有就**打数据源**，拿到后连同「实际牌价日」一起写进缓存。
3. 数据源也不可用（断网、接口挂了）时**降级**：用缓存里不晚于目标日期的最近一条。
   宁可用一条略旧但明确标注了日期的汇率，也不要让「录一张卡」这件事被网络卡死。

三层都拿不到才抛 FxError，由调用方决定是拒绝保存还是留空等以后补。
"""

from __future__ import annotations

import datetime as dt
import logging
from decimal import Decimal
from typing import Dict, Optional

from src import db, settings_store
from src.fx.providers import ProviderError, get_provider

log = logging.getLogger(__name__)

BASE = "JPY"
QUOTE = "CNY"

SETTING_SOURCE = "fx_source"
SETTING_AUTO = "fx_auto_fetch"


class FxError(RuntimeError):
    """汇率取不到。"""


def _source() -> str:
    return (settings_store.get(SETTING_SOURCE) or "ecb").strip().lower()


def auto_fetch_enabled() -> bool:
    return settings_store.get_bool(SETTING_AUTO, default=True)


def _cache_get(date: dt.date, base: str, quote: str, source: str) -> Optional[Dict]:
    return db.query_one(
        "SELECT rate_date, rate, source FROM fx_rates "
        "WHERE rate_date = %s AND base = %s AND quote = %s AND source = %s",
        (date, base, quote, source),
    )


def _cache_get_nearest(date: dt.date, base: str, quote: str, source: str) -> Optional[Dict]:
    """降级用：不晚于 date 的最近一条。"""
    return db.query_one(
        "SELECT rate_date, rate, source FROM fx_rates "
        "WHERE rate_date <= %s AND base = %s AND quote = %s AND source = %s "
        "ORDER BY rate_date DESC LIMIT 1",
        (date, base, quote, source),
    )


def _cache_put(date: dt.date, base: str, quote: str, source: str, rate: float) -> None:
    db.execute(
        "INSERT INTO fx_rates (rate_date, base, quote, rate, source) VALUES (%s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE rate = VALUES(rate), fetched_at = CURRENT_TIMESTAMP",
        (date, base, quote, round(float(rate), 8), source),
    )


def get_rate(
    date: dt.date | str,
    base: str = BASE,
    quote: str = QUOTE,
    allow_network: bool = True,
) -> Dict:
    """取某天的 base→quote 汇率。

    返回 ``{"rate": float, "rate_date": date, "source": str, "stale": bool}``。
    ``stale=True`` 表示走了降级路径，用的是比请求日期更早的一条牌价——界面上要提示，
    否则用户看到一个数字却不知道它其实不是那天的。
    """
    if isinstance(date, str):
        try:
            date = dt.date.fromisoformat(date.strip()[:10])
        except ValueError as exc:
            raise FxError(f"日期格式不正确：{date!r}") from exc
    source = _source()

    cached = _cache_get(date, base, quote, source)
    if cached:
        return {
            "rate": float(cached["rate"]),
            "rate_date": cached["rate_date"],
            "source": source,
            "stale": False,
        }

    if allow_network:
        try:
            rate, actual = get_provider(source).fetch(date, base, quote)
        except ProviderError as exc:
            log.warning("汇率源取 %s 失败，转降级：%s", date, exc)
        else:
            # 请求日 8/30（周日）实际拿到 8/28 的牌价时，两个日期都要落库：
            # 8/28 是真实牌价，8/30 建成别名，下次查 8/30 直接命中，不再打网络。
            _cache_put(actual, base, quote, source, rate)
            if actual != date:
                _cache_put(date, base, quote, source, rate)
            return {"rate": float(rate), "rate_date": actual, "source": source, "stale": False}

    fallback = _cache_get_nearest(date, base, quote, source)
    if fallback:
        return {
            "rate": float(fallback["rate"]),
            "rate_date": fallback["rate_date"],
            "source": source,
            "stale": True,
        }

    raise FxError(
        f"取不到 {date.isoformat()} 的 {base}→{quote} 汇率："
        f"本地无缓存，且汇率接口当前不可用。可以在卡片上手工填写汇率。"
    )


def latest(base: str = BASE, quote: str = QUOTE) -> Dict:
    return get_rate(dt.date.today(), base, quote)


def refresh_range(start: dt.date, end: dt.date, base: str = BASE, quote: str = QUOTE) -> int:
    """批量补齐一段日期的缓存，返回新写入的条数。用于「预热最近三个月」。"""
    if start > end:
        start, end = end, start
    source = _source()
    try:
        rates = get_provider(source).fetch_range(start, end, base, quote)
    except ProviderError as exc:
        raise FxError(str(exc)) from exc
    for day, rate in rates.items():
        _cache_put(day, base, quote, source, rate)
    return len(rates)


def convert(
    amount: Optional[Decimal | float],
    from_currency: str,
    to_currency: str,
    rate: Optional[Decimal | float],
) -> Optional[Decimal]:
    """按给定的 JPY→CNY 汇率换算金额。

    只认 JPY 和 CNY 两种币，且 ``rate`` 恒定是「1 JPY = ? CNY」。传进来的 rate 一律是
    卡片行上存好的快照，这个函数**不去取汇率**——利润展示必须完全由行内数据决定，
    否则同一条记录在不同时刻会算出不同的利润。
    """
    if amount is None:
        return None
    amount = Decimal(str(amount))
    from_currency = (from_currency or "").upper()
    to_currency = (to_currency or "").upper()
    if from_currency == to_currency:
        return amount
    if rate is None:
        return None
    rate = Decimal(str(rate))
    if rate <= 0:
        return None
    if from_currency == "JPY" and to_currency == "CNY":
        return amount * rate
    if from_currency == "CNY" and to_currency == "JPY":
        return amount / rate
    return None
