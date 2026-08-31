# -*- coding: utf-8 -*-
"""整机设备的领域逻辑：一次购入、拆件分售。

**与显卡（cards）的差别只有一处，但它决定了整个模型**：显卡是「一进一出」，
买价和卖价都在同一行上；整机是「一进多出」——花一笔总价买回一台机器，拆成
CPU、显卡、内存、硬盘、主板、电源分别挂出去，于是有**一个购入价、多个出售价**。

所以：

* ``devices``      —— 采购侧。只有一笔总价（purchase_amount）与国际运费。
* ``device_parts`` —— 出售侧。一台设备多行，每行一个出售价格；内存 / 硬盘这类
  一台机器里本来就有好几条的，就是好几行，行数不设上限。

**汇率**沿用与显卡完全一致的口径（见 src.cards 的表格）：购入价与国际运费跟着
设备的 ``purchase_fx_rate``；每个部件的出售价与国内运费跟着**该部件自己**的
``sale_fx_rate``——部件是分别在不同日子卖掉的，共用一个出售汇率会算错。

**利润**：收入 = Σ部件售价；成本 = 购入总价 + 国际运费 + Σ部件国内运费。
部件没卖完时利润仍照此计算，但会带上 ``settled=False``——那是「已回本多少」，
不是最终盈亏。前端据此区分，避免把中途的数字当成结论。

**成本不往部件上分摊**：整机只有一个总价，任何「这条内存成本多少」的拆法都是
硬编出来的假精度（按售价比例分？按市场价分？两种分法能差出一倍），不如不给。
需要看单件贡献时看它的售价与净收入即可。

**资金池**（``fund_source='pool'``）与显卡完全同一套：这台机器的日元从池里出，采购侧
成本就不是「金额 ÷ 购入日牌价」，而是被吃掉的那几批注资各按各自的换汇价折算再相加。
分摊由 src.funds 按 FIFO 算好后回写在 ``pool_purchase_cny`` / ``pool_intl_cny`` 上，
这里直接取用。出售侧不受影响：部件卖的是人民币，仍走各自的 ``sale_fx_rate``。
"""

from __future__ import annotations

import datetime as dt
import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from src import db
from src.fx import FxError, get_rate
# 金额换算与序列化的口径必须和显卡完全一致，共用同一份实现而不是再抄一遍：
# 抄一份的下场是某天只改了其中一处，两个页面的合计从此对不上。
from src.cards import _dec, _iso, _purchase_side, _round_rate, _to_cny, uses_pool
from src.schema import CARD_STATUSES, DEVICE_PART_TYPES

log = logging.getLogger(__name__)

_CENT = Decimal("0.01")
_ZERO = Decimal("0")

# 部件在表单 / 详情里的默认排序：先按 DEVICE_PART_TYPES 的顺序，同类再按 sort_order。
_TYPE_ORDER = {name: i for i, name in enumerate(DEVICE_PART_TYPES)}


# ── 管理编号 ────────────────────────────────────────────────────────────── #

def next_mgmt_no(year: Optional[int] = None) -> str:
    """``DEV-2026-0001``。与显卡分开编号，一眼能看出是整机还是单卡。

    同样用 ``MAX(序号)+1`` 而不是 ``COUNT(*)+1``：删掉一台后 COUNT 会退回去，
    下一台就会撞上 mgmt_no 的唯一索引。
    """
    year = year or dt.date.today().year
    prefix = f"DEV-{year}-"
    row = db.query_one(
        "SELECT MAX(CAST(SUBSTRING(mgmt_no, %s) AS UNSIGNED)) AS max_seq "
        "FROM devices WHERE mgmt_no LIKE %s",
        (len(prefix) + 1, prefix + "%"),
    )
    max_seq = int((row or {}).get("max_seq") or 0)
    return f"{prefix}{max_seq + 1:04d}"


# ── 汇率快照 ────────────────────────────────────────────────────────────── #

def resolve_rates(dates: List[Optional[dt.date]]) -> Dict[str, Any]:
    """一次把用到的日期全取完，返回 ``{日期: 牌价结果}`` 与警告列表。

    整机保存一次要取的汇率不止一个（购入日 + 每个部件各自的出售日），逐个现取会把
    同一天重复查好几遍。这里先去重再取；``fx.get_rate`` 本身带库内缓存，去重后基本
    只剩真正的首次查询。取不到不抛异常——录入不该因为汇率接口抽风而中断。
    """
    out: Dict[str, Any] = {"rates": {}, "warnings": []}
    for value in sorted({d for d in dates if d}):
        try:
            result = get_rate(value)
        except FxError as exc:
            out["warnings"].append(f"{value} 汇率获取失败：{exc}")
            continue
        out["rates"][value] = result
        if result["stale"]:
            out["warnings"].append(f"{value} 无牌价，已回退到 {result['rate_date']} 的汇率")
        elif result["rate_date"] != value:
            out["warnings"].append(f"{value} 是非交易日，采用 {result['rate_date']} 的牌价")
    return out


def rate_for(resolved: Dict[str, Any], date_value: Optional[dt.date]) -> Tuple[Any, Any]:
    """从 ``resolve_rates`` 的结果里取某天的 (汇率, 牌价日)，没取到就是 (None, None)。"""
    if not date_value:
        return None, None
    result = resolved["rates"].get(date_value)
    if not result:
        return None, None
    return result["rate"], result["rate_date"]


# ── 金额换算 ────────────────────────────────────────────────────────────── #

def _float(value: Optional[Decimal]) -> Optional[float]:
    if value is None:
        return None
    return float(value.quantize(_CENT, rounding=ROUND_HALF_UP))


def part_money(part: Dict[str, Any]) -> Dict[str, Any]:
    """单个部件的出售侧金额。国内运费也走本部件的出售汇率（发货与成交同期）。"""
    rate = part.get("sale_fx_rate")
    sale = _to_cny(part.get("sale_amount"), part.get("sale_currency"), rate)
    domestic = _to_cny(
        part.get("domestic_shipping_amount"), part.get("domestic_shipping_currency"), rate
    )
    net: Optional[Decimal] = None
    if sale is not None:
        net = sale - (domestic or _ZERO)
    return {
        "sale_cny": _float(sale),
        "domestic_shipping_cny": _float(domestic),
        # 净收入 = 售价 − 国内运费。不减成本：整机只有一个总价，摊到单件是假精度。
        "net_cny": _float(net),
        "sold": _dec(part.get("sale_amount")) is not None,
        # 填了金额却折不出来（缺汇率）——前端要显示提示，而不是一个空格子
        "incomplete": (
            (_dec(part.get("sale_amount")) is not None and sale is None)
            or (_dec(part.get("domestic_shipping_amount")) is not None and domestic is None)
        ),
    }


def _part_of(raw: Any, converted: Optional[Decimal]) -> Tuple[Decimal, bool]:
    """(计入合计的值, 是否缺口)。压根没填的按 0 计，填了却折不出来才算缺口。"""
    if _dec(raw) is None:
        return _ZERO, False
    if converted is None:
        return _ZERO, True
    return converted, False


def compute_money(device: Dict[str, Any], parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """整台设备的成本 / 收入 / 利润（全部折成人民币）。

    与显卡同一条原则：某项该折算却折不出来（缺汇率）时，含它的合计返回 None 而不是
    当 0——把缺失当零会算出一个看着正常、实际严重偏高的利润。
    """
    p_rate = device.get("purchase_fx_rate")
    # 走资金池时这两项取 FIFO 分摊的结果，不再用购入日牌价（与显卡同一个函数）
    purchase = _purchase_side(
        device, "purchase_amount", "purchase_currency", "pool_purchase_cny", p_rate)
    intl = _purchase_side(
        device, "intl_shipping_amount", "intl_shipping_currency", "pool_intl_cny", p_rate)

    cost_total = _ZERO
    cost_incomplete = False
    for raw, converted in (
        (device.get("purchase_amount"), purchase),
        (device.get("intl_shipping_amount"), intl),
    ):
        value, missing = _part_of(raw, converted)
        cost_total += value
        cost_incomplete = cost_incomplete or missing

    revenue_total = _ZERO
    revenue_incomplete = False
    domestic_total = _ZERO
    sold_count = 0
    for part in parts:
        money = part_money(part)
        if money["sold"]:
            sold_count += 1
        sale_value, sale_missing = _part_of(part.get("sale_amount"), _dec(money["sale_cny"]))
        dom_value, dom_missing = _part_of(
            part.get("domestic_shipping_amount"), _dec(money["domestic_shipping_cny"])
        )
        revenue_total += sale_value
        domestic_total += dom_value
        revenue_incomplete = revenue_incomplete or sale_missing
        cost_incomplete = cost_incomplete or dom_missing
    cost_total += domestic_total

    part_count = len(parts)
    has_revenue = sold_count > 0

    profit: Optional[Decimal] = None
    margin: Optional[float] = None
    recovery: Optional[float] = None
    if not cost_incomplete and not revenue_incomplete:
        profit = revenue_total - cost_total
        if revenue_total > 0:
            margin = float((profit / revenue_total * 100).quantize(_CENT, rounding=ROUND_HALF_UP))
        if cost_total > 0:
            recovery = float(
                (revenue_total / cost_total * 100).quantize(_CENT, rounding=ROUND_HALF_UP)
            )

    return {
        "purchase_cny": _float(purchase),
        "intl_shipping_cny": _float(intl),
        "domestic_shipping_cny": _float(domestic_total),
        "sale_cny": _float(revenue_total) if has_revenue else None,
        "cost_total_cny": None if cost_incomplete else _float(cost_total),
        "profit_cny": _float(profit),
        "profit_margin": margin,
        # 回本率 = 已收回 ÷ 总成本。部件没卖完时它比「利润」更有意义
        "recovery": recovery,
        "part_count": part_count,
        "sold_count": sold_count,
        # 部件全部卖出，利润才是最终数字；否则它只是「目前收回了多少」
        "settled": part_count > 0 and sold_count == part_count,
        "incomplete": cost_incomplete or revenue_incomplete,
        # 采购成本是按资金池的注资汇率算的（前端据此标注，别让人以为用的是当日牌价）
        "from_pool": uses_pool(device),
        "pool_fx_rate": _round_rate(device.get("pool_fx_rate")),
    }


# ── 序列化 ──────────────────────────────────────────────────────────────── #

def serialize_part(row: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(row)
    for key in ("sale_date", "sale_fx_date", "created_at", "updated_at"):
        out[key] = _iso(row.get(key))
    for key in ("sale_amount", "domestic_shipping_amount", "sale_fx_rate"):
        value = row.get(key)
        out[key] = float(value) if value is not None else None
    out["quantity"] = int(row.get("quantity") or 1)
    out["money"] = part_money(row)
    return out


def serialize(row: Dict[str, Any], parts: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """数据库行 → API 响应。Decimal / date 都不是 JSON 原生类型，必须显式转。"""
    parts = parts or []
    out: Dict[str, Any] = dict(row)
    for key in ("purchase_date", "purchase_fx_date", "created_at", "updated_at"):
        out[key] = _iso(row.get(key))
    for key in ("purchase_amount", "intl_shipping_amount", "purchase_fx_rate",
                "pool_purchase_cny", "pool_intl_cny", "pool_fx_rate"):
        value = row.get(key)
        out[key] = float(value) if value is not None else None
    out["fund_source"] = row.get("fund_source") or "own"
    out["money"] = compute_money(row, parts)
    out["parts"] = [serialize_part(p) for p in parts]
    return out


def load_parts(device_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
    """批量取多台设备的部件，按 device_id 分组。

    列表页每行都要算成本与利润，而那要用到该行的全部部件。逐台查一次是典型的
    N+1——20 台就是 20 次往返，这里一次 IN 查询全取回来再分组。
    """
    if not device_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(device_ids))
    rows = db.query(
        "SELECT * FROM device_parts WHERE device_id IN ({ph}) "
        "ORDER BY device_id, sort_order, id".format(ph=placeholders),
        device_ids,
    )
    grouped: Dict[int, List[Dict[str, Any]]] = {did: [] for did in device_ids}
    for row in rows:
        grouped.setdefault(row["device_id"], []).append(row)
    return grouped


def type_rank(part_type: Optional[str]) -> int:
    """部件类型的展示顺序，未知类型排最后。"""
    return _TYPE_ORDER.get(part_type or "", len(_TYPE_ORDER))


def validate_status(status: Optional[str]) -> str:
    status = (status or "purchased").strip()
    if status not in CARD_STATUSES:
        raise ValueError(f"未知状态：{status}")
    return status
