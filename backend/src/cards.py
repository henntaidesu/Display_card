# -*- coding: utf-8 -*-
"""显卡的领域逻辑：管理编号、汇率快照、成本与利润换算。

**金额与汇率的对应关系**（整套系统的核心约定，改这里之前先想清楚）：

| 金额         | 用哪个汇率        | 理由                                     |
|--------------|-------------------|------------------------------------------|
| 购入价       | purchase_fx_rate  | 钱是买卡那天付的                         |
| 国际运费     | purchase_fx_rate  | 跟着采购一起发生，与采购同期结汇         |
| 国内运费     | sale_fx_rate      | 卖出去才发生的支出，与售价同期            |
| 出售价       | sale_fx_rate      | 钱是成交那天收的                         |

汇率一旦取到就**写死在卡片行里**（purchase_fx_rate / sale_fx_rate），之后再也不重算。
不快照的话，同一张卡今天算出来的利润和昨天不一样——汇率每天都在动，而已经发生的
交易的盈亏是不会变的。要改只能显式改（fx_manual=1，自动刷新会跳过它）。
"""

from __future__ import annotations

import datetime as dt
import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from src import db
from src.fx import FxError, get_rate
from src.schema import CARD_STATUSES

log = logging.getLogger(__name__)

_CENT = Decimal("0.01")

# 走到这些状态说明卡已经出手了，出售侧金额才算数
SOLD_STATUSES = {"received", "paid"}


# ── 管理编号 ────────────────────────────────────────────────────────────── #

def next_mgmt_no(year: Optional[int] = None) -> str:
    """生成 ``GPU-2026-0001`` 形式的编号，按年重新计数。

    用 ``MAX(序号)+1`` 而不是 ``COUNT(*)+1``：删掉一张卡后 COUNT 会退回去，
    下一张新卡就会拿到一个已经用过的编号，而 mgmt_no 上有唯一索引，插入直接失败。
    """
    year = year or dt.date.today().year
    prefix = f"GPU-{year}-"
    row = db.query_one(
        "SELECT MAX(CAST(SUBSTRING(mgmt_no, %s) AS UNSIGNED)) AS max_seq "
        "FROM cards WHERE mgmt_no LIKE %s",
        (len(prefix) + 1, prefix + "%"),
    )
    max_seq = int((row or {}).get("max_seq") or 0)
    return f"{prefix}{max_seq + 1:04d}"


# ── 汇率快照 ────────────────────────────────────────────────────────────── #

def resolve_fx(
    purchase_date: Optional[dt.date],
    sale_date: Optional[dt.date],
    allow_network: bool = True,
) -> Dict[str, Any]:
    """按买入日 / 卖出日各取一次 JPY→CNY 汇率。

    取不到不抛异常，只把对应字段留空并在 ``warnings`` 里说明。理由：录卡这件事不该
    因为汇率接口抽风而做不下去——先把卡存进去，汇率之后用「刷新汇率」补即可。
    """
    out: Dict[str, Any] = {
        "purchase_fx_rate": None, "purchase_fx_date": None,
        "sale_fx_rate": None, "sale_fx_date": None,
        "warnings": [],
    }
    for date_value, rate_key, date_key, label in (
        (purchase_date, "purchase_fx_rate", "purchase_fx_date", "购入日"),
        (sale_date, "sale_fx_rate", "sale_fx_date", "出售日"),
    ):
        if not date_value:
            continue
        try:
            result = get_rate(date_value, allow_network=allow_network)
        except FxError as exc:
            out["warnings"].append(f"{label}汇率获取失败：{exc}")
            continue
        out[rate_key] = result["rate"]
        out[date_key] = result["rate_date"]
        if result["stale"]:
            out["warnings"].append(
                f"{label} {date_value} 无牌价，已回退到 {result['rate_date']} 的汇率"
            )
        elif result["rate_date"] != date_value:
            out["warnings"].append(
                f"{label} {date_value} 是非交易日，采用 {result['rate_date']} 的牌价"
            )
    return out


# ── 金额换算 ────────────────────────────────────────────────────────────── #

def _dec(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _to_cny(amount: Any, currency: str, rate: Any) -> Optional[Decimal]:
    """把一笔金额折成人民币。JPY 需要汇率，CNY 原样返回。

    rate 是「1 人民币 = rate 日元」（约 23.76，与实际换汇口径一致）。所以日元金额换人民币
    是**除以** rate，而不是乘：390000 日元 ÷ 23.165 = 16836 元。
    """
    amount = _dec(amount)
    if amount is None:
        return None
    if (currency or "CNY").upper() == "CNY":
        return amount
    rate = _dec(rate)
    if rate is None or rate <= 0:
        return None  # 汇率还没取到：宁可显示「—」，也不要拿一个错的数字去凑
    return amount / rate


def _round(value: Optional[Decimal]) -> Optional[float]:
    if value is None:
        return None
    return float(value.quantize(_CENT, rounding=ROUND_HALF_UP))


def compute_money(row: Dict[str, Any]) -> Dict[str, Any]:
    """算出这张卡的成本、收入、利润（全部折成人民币）。

    任何一项该折算却折不出来（缺汇率）时，含它的合计一律返回 None 而不是当 0 处理——
    把缺失当零会算出一个看起来正常、实际严重偏高的利润，比留空危险得多。
    """
    p_rate = row.get("purchase_fx_rate")
    s_rate = row.get("sale_fx_rate")

    purchase = _to_cny(row.get("purchase_amount"), row.get("purchase_currency"), p_rate)
    intl = _to_cny(row.get("intl_shipping_amount"), row.get("intl_shipping_currency"), p_rate)
    domestic = _to_cny(row.get("domestic_shipping_amount"), row.get("domestic_shipping_currency"), s_rate)
    revenue = _to_cny(row.get("sale_amount"), row.get("sale_currency"), s_rate)

    # 只有「填了金额但折不出来」才算缺口；压根没填的项按 0 计入合计。
    def part(raw: Any, converted: Optional[Decimal]) -> tuple[Decimal, bool]:
        if _dec(raw) is None:
            return Decimal("0"), False
        if converted is None:
            return Decimal("0"), True
        return converted, False

    cost_total = Decimal("0")
    cost_incomplete = False
    for raw, converted in (
        (row.get("purchase_amount"), purchase),
        (row.get("intl_shipping_amount"), intl),
        (row.get("domestic_shipping_amount"), domestic),
    ):
        value, missing = part(raw, converted)
        cost_total += value
        cost_incomplete = cost_incomplete or missing

    revenue_value, revenue_missing = part(row.get("sale_amount"), revenue)
    has_revenue = _dec(row.get("sale_amount")) is not None

    profit: Optional[Decimal] = None
    margin: Optional[float] = None
    if has_revenue and not revenue_missing and not cost_incomplete:
        profit = revenue_value - cost_total
        if revenue_value > 0:
            margin = float((profit / revenue_value * 100).quantize(_CENT, rounding=ROUND_HALF_UP))

    return {
        "purchase_cny": _round(purchase),
        "intl_shipping_cny": _round(intl),
        "domestic_shipping_cny": _round(domestic),
        "sale_cny": _round(revenue),
        "cost_total_cny": None if cost_incomplete else _round(cost_total),
        "profit_cny": _round(profit),
        "profit_margin": margin,
        # 缺汇率导致算不出来时前端要显示提示，而不是一个空白格子
        "incomplete": cost_incomplete or (has_revenue and revenue_missing),
    }


# ── 序列化 ──────────────────────────────────────────────────────────────── #

def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return str(value)


def serialize(row: Dict[str, Any], media: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """把数据库行转成 API 响应。

    Decimal 和 date 都不是 JSON 原生类型，必须显式转——直接丢给 FastAPI 会在序列化
    阶段报错，而那个错的堆栈完全指不到是哪个字段的问题。
    """
    out: Dict[str, Any] = dict(row)
    for key in ("purchase_date", "sale_date", "purchase_fx_date", "sale_fx_date"):
        out[key] = _iso(row.get(key))
    for key in ("created_at", "updated_at"):
        out[key] = _iso(row.get(key))
    for key in (
        "purchase_amount", "intl_shipping_amount",
        "domestic_shipping_amount", "sale_amount",
        "purchase_fx_rate", "sale_fx_rate",
    ):
        value = row.get(key)
        out[key] = float(value) if value is not None else None
    out["fx_manual"] = bool(row.get("fx_manual"))
    out["money"] = compute_money(row)
    if media is not None:
        out["media"] = media
    return out


def load_media(card_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
    """批量取多张卡的媒体，按 card_id 分组。

    列表页每行都要显示一张封面图。逐行查一次是典型的 N+1——20 行就是 20 次往返，
    这里一次 IN 查询全取回来再分组。
    """
    if not card_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(card_ids))
    rows = db.query(
        f"SELECT id, card_id, category, kind, stored_name, public_url, filename, "
        f"mime_type, size_bytes, sort_order, created_at "
        f"FROM card_media WHERE card_id IN ({placeholders}) "
        f"ORDER BY card_id, category, sort_order, id",
        card_ids,
    )
    grouped: Dict[int, List[Dict[str, Any]]] = {cid: [] for cid in card_ids}
    for row in rows:
        item = dict(row)
        item["created_at"] = _iso(row.get("created_at"))
        item["size_bytes"] = int(row["size_bytes"]) if row.get("size_bytes") is not None else None
        grouped.setdefault(row["card_id"], []).append(item)
    return grouped


def log_status(card_id: int, from_status: Optional[str], to_status: str, note: str = "") -> None:
    if from_status == to_status:
        return
    db.execute(
        "INSERT INTO card_status_logs (card_id, from_status, to_status, note) "
        "VALUES (%s, %s, %s, %s)",
        (card_id, from_status, to_status, (note or "")[:500]),
    )


def validate_status(status: Optional[str]) -> str:
    status = (status or "purchased").strip()
    if status not in CARD_STATUSES:
        raise ValueError(f"未知状态：{status}")
    return status
