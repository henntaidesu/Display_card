# -*- coding: utf-8 -*-
"""库存合并列表：显卡与整机设备放在同一张表里，用 ``kind`` 区分。

**为什么要有这个模块**：两种货的数据结构差得远——显卡是一进一出（买价卖价在同一行），
整机是一进多出（一笔总价，拆件分售，出售价在 device_parts 上）。硬塞进一张表会让两边
都别扭。但**看库存的人不关心这个**：他要的是「我手上一共有什么、花了多少、回来多少」，
按类型分成两个页面等于每次都要看两遍再自己加一次。

所以底层仍是 cards / devices 两套表与两套 CRUD，只在这里把它们**规范化成同一种行**
（编号、名称、状态、日期、成本、收入、盈亏），再统一筛选、排序、分页。

**为什么在 Python 里排序分页而不是 SQL**：两张表结构不同，UNION 要先把列一一对齐，
而成本 / 利润根本不是列——它们是按汇率快照算出来的（见 cards.compute_money）。想在
SQL 里按利润排序就得把整套换算逻辑再用 SQL 写一遍，两份实现迟早对不上。这个系统的
量级是几百行，全取回来在内存里排完再切页，快得多也稳得多。
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from src import cards, db, devices
from src.auth import require_auth
from src.schema import CARD_STATUSES

log = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["inventory"], dependencies=[Depends(require_auth)])

# 列表行的类型。card / device 是顶层行，part 是整机展开后的二级行——它们共用同一套
# 列，所以在这里就规范化成同一种形状，前端不必为二级行另写一张表。
KIND_CARD = "card"
KIND_DEVICE = "device"
KIND_PART = "part"

# 允许的排序列。全部是**规范化之后**的字段名，两种类型共用同一套。
_SORT_KEYS = {
    "created_at", "updated_at", "purchase_date", "sale_date",
    "mgmt_no", "title", "status", "cost_total_cny", "sale_cny", "profit_cny",
}


# ── 规范化：两种货 → 同一种行 ───────────────────────────────────────────── #

def _card_item(row: Dict[str, Any], media: List[Dict[str, Any]]) -> Dict[str, Any]:
    data = cards.serialize(row, media)
    money = data["money"]
    return {
        # 行标识。卡片与整机的 id 各自从 1 开始，二级行还要和它们混在一张表里，
        # 不带类型前缀会撞。el-table 的 row-key / 树形展开都靠它。
        "row_key": f"{KIND_CARD}-{row['id']}",
        "kind": KIND_CARD,
        "id": row["id"],
        "mgmt_no": row["mgmt_no"],
        "title": " ".join(x for x in (row.get("brand"), row.get("model")) if x) or None,
        "subtitle": row.get("vram"),
        "status": row["status"],
        "source_platform": row.get("source_platform"),
        "purchase_date": data["purchase_date"],
        "sale_date": data["sale_date"],
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
        # 显卡没有「部件」概念：一张卡就是一件，卖了就是 1/1
        "part_count": 1,
        "sold_count": 1 if row.get("sale_amount") is not None else 0,
        "sold": row["status"] in cards.SOLD_STATUSES or row.get("sale_amount") is not None,
        # 一张卡卖掉就没有后续了，所以「卖了 = 已结清」
        "settled": row.get("sale_amount") is not None,
        "cost_total_cny": money["cost_total_cny"],
        "sale_cny": money["sale_cny"],
        "profit_cny": money["profit_cny"],
        "incomplete": money["incomplete"],
        "from_pool": money["from_pool"],
        "media": data["media"],
        # 编辑弹窗要的完整对象，前端不必为了改一行再单独查一次
        "data": data,
    }


def _part_row(part: Dict[str, Any], device_id: int) -> Dict[str, Any]:
    """把一个部件规范化成**和顶层行同样的形状**，作为整机的二级行。

    不适用的列一律给 None，前端统一显示成「—」：部件没有购入日（整机是一口价买的），
    也没有单件成本——总价不往部件上摊（理由见 src.devices 的模块文档），所以「总成本」
    和「利润」这两列在部件行上是空的，只有出售侧的数字。
    """
    money = part["money"]
    title = " ".join(x for x in (part.get("brand"), part.get("model"), part.get("spec")) if x)
    return {
        "row_key": f"{KIND_PART}-{part['id']}",
        "kind": KIND_PART,
        "id": part["id"],
        # 点二级行时要能打开它所属的那台设备
        "device_id": device_id,
        "part_type": part["part_type"],
        "quantity": part["quantity"],
        "mgmt_no": None,
        "title": title or None,
        "subtitle": None,
        "status": part["status"],
        "source_platform": None,
        "purchase_date": None,
        "sale_date": part["sale_date"],
        "created_at": part["created_at"],
        "updated_at": part["updated_at"],
        "part_count": None,
        "sold_count": None,
        "sold": money["sold"],
        "settled": money["sold"],
        "cost_total_cny": None,
        "sale_cny": money["sale_cny"],
        # 净收入 = 售价 − 国内运费。放在这儿供前端在「已收回」下方标一行小字，
        # 「已收回」本身仍取售价，二级行加起来才等于整机那一行。
        "net_cny": money["net_cny"],
        "domestic_shipping_cny": money["domestic_shipping_cny"],
        "profit_cny": None,
        "incomplete": money["incomplete"],
        "from_pool": False,
        "media": [],
        "data": None,
    }


def _device_item(row: Dict[str, Any], parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    data = devices.serialize(row, parts)
    money = data["money"]
    # 整机没有单一的「出售日期」——部件是分批卖的。列表里显示最后成交的那天，
    # 它才是「这台机器进行到哪儿了」的答案。
    sale_dates = [p["sale_date"] for p in data["parts"] if p["sale_date"]]
    item = {
        "row_key": f"{KIND_DEVICE}-{row['id']}",
        "kind": KIND_DEVICE,
        "id": row["id"],
        "mgmt_no": row["mgmt_no"],
        "title": row.get("title"),
        "subtitle": None,
        "status": row["status"],
        "source_platform": row.get("source_platform"),
        "purchase_date": data["purchase_date"],
        "sale_date": max(sale_dates) if sale_dates else None,
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
        "part_count": money["part_count"],
        "sold_count": money["sold_count"],
        "sold": money["sold_count"] > 0,
        "settled": money["settled"],
        "cost_total_cny": money["cost_total_cny"],
        "sale_cny": money["sale_cny"],
        "profit_cny": money["profit_cny"],
        "incomplete": money["incomplete"],
        "from_pool": money["from_pool"],
        "media": [],
        "data": data,
    }
    # 二级行。没有部件时**不带 children 这个键**——给个空数组的话 el-table 仍会画出
    # 一个点开是空的展开箭头。
    if data["parts"]:
        item["children"] = [_part_row(p, row["id"]) for p in data["parts"]]
    return item


# ── 筛选 ────────────────────────────────────────────────────────────────── #

def _statuses(status: Optional[str]) -> List[str]:
    if not status:
        return []
    return [s.strip() for s in status.split(",") if s.strip() in CARD_STATUSES]


def _fetch_cards(
    keyword: Optional[str],
    statuses: List[str],
    brand: Optional[str],
    source_platform: Optional[str],
    purchase_from: Optional[dt.date],
    purchase_to: Optional[dt.date],
) -> List[Dict[str, Any]]:
    where: List[str] = ["is_draft = 0"]
    params: List[Any] = []
    if keyword:
        like = f"%{keyword.strip()}%"
        where.append(
            "(mgmt_no LIKE %s OR brand LIKE %s OR model LIKE %s "
            "OR serial_no LIKE %s OR seller LIKE %s OR order_no LIKE %s)"
        )
        params.extend([like] * 6)
    if statuses:
        where.append("status IN ({ph})".format(ph=", ".join(["%s"] * len(statuses))))
        params.extend(statuses)
    if brand:
        where.append("brand = %s")
        params.append(brand.strip())
    if source_platform:
        where.append("source_platform = %s")
        params.append(source_platform.strip().lower())
    if purchase_from:
        where.append("purchase_date >= %s")
        params.append(purchase_from)
    if purchase_to:
        where.append("purchase_date <= %s")
        params.append(purchase_to)

    rows = db.query("SELECT * FROM cards WHERE " + " AND ".join(where), params)
    media_map = cards.load_media([r["id"] for r in rows])
    return [_card_item(r, media_map.get(r["id"], [])) for r in rows]


def _fetch_devices(
    keyword: Optional[str],
    statuses: List[str],
    brand: Optional[str],
    source_platform: Optional[str],
    purchase_from: Optional[dt.date],
    purchase_to: Optional[dt.date],
) -> List[Dict[str, Any]]:
    where: List[str] = ["is_draft = 0"]
    params: List[Any] = []
    if keyword:
        like = f"%{keyword.strip()}%"
        # 部件里的品牌 / 型号 / 序列号也要能搜到：找一台机器往往是从「哪台里有那块 4090」
        # 反推的，只搜设备自己的字段等于搜不到。
        where.append(
            "(mgmt_no LIKE %s OR title LIKE %s OR seller LIKE %s OR order_no LIKE %s "
            " OR EXISTS (SELECT 1 FROM device_parts p WHERE p.device_id = devices.id "
            "            AND (p.brand LIKE %s OR p.model LIKE %s OR p.spec LIKE %s "
            "                 OR p.serial_no LIKE %s)))"
        )
        params.extend([like] * 8)
    if statuses:
        where.append("status IN ({ph})".format(ph=", ".join(["%s"] * len(statuses))))
        params.extend(statuses)
    if brand:
        # 整机本身没有品牌，按「里面有这个品牌的部件」来匹配
        where.append(
            "EXISTS (SELECT 1 FROM device_parts p WHERE p.device_id = devices.id AND p.brand = %s)"
        )
        params.append(brand.strip())
    if source_platform:
        where.append("source_platform = %s")
        params.append(source_platform.strip().lower())
    if purchase_from:
        where.append("purchase_date >= %s")
        params.append(purchase_from)
    if purchase_to:
        where.append("purchase_date <= %s")
        params.append(purchase_to)

    rows = db.query("SELECT * FROM devices WHERE " + " AND ".join(where), params)
    parts_map = devices.load_parts([r["id"] for r in rows])
    return [_device_item(r, parts_map.get(r["id"], [])) for r in rows]


def _collect(
    kind: Optional[str],
    keyword: Optional[str],
    status: Optional[str],
    brand: Optional[str],
    source_platform: Optional[str],
    purchase_from: Optional[dt.date],
    purchase_to: Optional[dt.date],
) -> List[Dict[str, Any]]:
    """按筛选条件取出两类库存，合成一个列表。列表与统计共用它，口径永远一致。"""
    statuses = _statuses(status)
    # 指定了状态却一个合法值都没有：说明筛的是不存在的状态，直接返回空，
    # 而不是把条件丢掉当「不筛」——那会让人以为筛选没生效。
    if status and not statuses:
        return []
    items: List[Dict[str, Any]] = []
    args = (keyword, statuses, brand, source_platform, purchase_from, purchase_to)
    if kind != KIND_DEVICE:
        items.extend(_fetch_cards(*args))
    if kind != KIND_CARD:
        items.extend(_fetch_devices(*args))
    return items


def _sort(items: List[Dict[str, Any]], sort_by: str, sort_dir: str) -> List[Dict[str, Any]]:
    """按规范化后的字段排序。

    缺失值（没卖出去所以没有出售日、缺汇率所以没有利润）一律排在最后，无论升序降序：
    把 NULL 当 0 排会让「算不出来的」混进「利润最低的」里，那是会看错的排序。
    """
    key = sort_by if sort_by in _SORT_KEYS else "created_at"
    reverse = str(sort_dir).lower() != "asc"

    def sort_key(item: Dict[str, Any]):
        value = item.get(key)
        missing = value is None
        # 元组第一位专管「缺失值垫底」，并跟着 reverse 取反：升序时缺失取 True（排最大），
        # 降序时取 False（排最小、翻转后到末尾），两个方向下都落在最后。
        # 第二位只在第一位相同时才参与比较，也就是只在「都缺失」或「都不缺失」之间比，
        # 因此 0 与字符串永远不会撞上（每个排序列自己的类型是固定的）。
        return (missing != reverse, 0 if missing else value)

    return sorted(items, key=sort_key, reverse=reverse)


@router.get("/stats")
def stats(
    kind: Optional[str] = Query(default=None, description="card / device，留空为全部"),
    keyword: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    brand: Optional[str] = Query(default=None),
    source_platform: Optional[str] = Query(default=None),
    purchase_from: Optional[dt.date] = Query(default=None),
    purchase_to: Optional[dt.date] = Query(default=None),
):
    """顶部统计：对**当前筛选下的全部库存**（不只当前页）汇总，显卡与整机合在一起。

    金额一律用各自领域模块算好的结果，缺汇率的项不当 0 计入（见 compute_money）。
    """
    items = _collect(kind, keyword, status, brand, source_platform, purchase_from, purchase_to)

    def _sum(key: str) -> float:
        return round(sum(i[key] for i in items if i[key] is not None), 2)

    card_count = sum(1 for i in items if i["kind"] == KIND_CARD)
    settled = sum(1 for i in items if i["settled"])
    total_cost = _sum("cost_total_cny")
    total_revenue = _sum("sale_cny")
    return {
        "total": len(items),
        "cards": card_count,
        "devices": len(items) - card_count,
        # 「在库」= 还没卖完的（显卡没卖出、整机部件没出完）
        "in_stock": len(items) - settled,
        "settled": settled,
        "total_cost_cny": total_cost,
        "total_revenue_cny": total_revenue,
        # 已收回 − 已花出去。含未卖完的整机，所以是「到目前为止的盈亏」
        "total_profit_cny": round(total_revenue - total_cost, 2),
        "recovery": round(total_revenue / total_cost * 100, 2) if total_cost else None,
        "incomplete": sum(1 for i in items if i["incomplete"]),
    }


@router.get("")
def list_inventory(
    kind: Optional[str] = Query(default=None, description="card / device，留空为全部"),
    keyword: Optional[str] = Query(default=None, description="编号/型号/序列号/卖家/部件 模糊匹配"),
    status: Optional[str] = Query(default=None),
    brand: Optional[str] = Query(default=None),
    source_platform: Optional[str] = Query(default=None),
    purchase_from: Optional[dt.date] = Query(default=None),
    purchase_to: Optional[dt.date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
):
    items = _collect(kind, keyword, status, brand, source_platform, purchase_from, purchase_to)
    items = _sort(items, sort_by, sort_dir)
    start = (page - 1) * page_size
    return {
        "items": items[start:start + page_size],
        "total": len(items),
        "page": page,
        "page_size": page_size,
    }
