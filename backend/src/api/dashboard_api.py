# -*- coding: utf-8 -*-
"""概览页统计。

所有金额统计都在 **Python 侧**用 cards.compute_money 算，而不是写成一条 SQL 的
SUM。因为「金额 × 该行自己的汇率快照，且缺汇率时不当 0」这套规则在 SQL 里要写成
一坨 CASE WHEN，还会和 cards.py 里的规则各自演化——两处算出来的利润对不上时，
没人说得清哪个是对的。数据量是几百到几千行，一次全读回来毫无压力。

入账口径（整页统一，KPI 与图表都按这个走）：
- **成本**记在「购入日」——钱是那天花出去的；
- **收入 / 利润**记在「出售日」——这笔钱是那天赚到的。
所以同一区间里的「利润」并不等于「收入 − 成本」（卡可能上个月买、这个月卖），
两者是各自独立的指标，前端不要拿它们相减。
"""

from __future__ import annotations

import datetime as dt
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from src import cards, db
from src.auth import require_auth
from src.cards import SOLD_STATUSES
from src.schema import CARD_STATUSES, SOURCE_PLATFORMS

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_auth)])

# 区间长过这个天数就改按月分桶：几百根柱子挤在一张图里，刻度会糊成一片
_MONTH_BUCKET_DAYS = 120

# 「待处理」面板关心的状态：流程没走完、需要人去推一把的那些
_WORK_STATUSES = ["pending_test", "test_failed", "returning", "returned", "forwarding", "received"]


def _sum(values: List[Any]) -> float:
    return round(sum(v for v in values if v is not None), 2)


def _is_sold(row: Dict[str, Any]) -> bool:
    return row["status"] in SOLD_STATUSES or row.get("sale_amount") is not None


def _bucket_key(day: dt.date, granularity: str) -> str:
    return day.strftime("%Y-%m") if granularity == "month" else day.isoformat()


def _period(rows: List[Dict[str, Any]], money: Dict[int, Dict[str, Any]],
            start: dt.date, end: dt.date) -> Dict[str, Any]:
    """一个区间的 KPI：成本按购入日入账，收入与利润按出售日入账。"""
    cost_values, revenue_values, profit_values = [], [], []
    bought = sold = 0
    for row in rows:
        m = money[row["id"]]
        purchase_date = row.get("purchase_date")
        sale_date = row.get("sale_date")
        if purchase_date and start <= purchase_date <= end:
            bought += 1
            cost_values.append(m["cost_total_cny"])
        if sale_date and start <= sale_date <= end and _is_sold(row):
            sold += 1
            revenue_values.append(m["sale_cny"])
            profit_values.append(m["profit_cny"])
    revenue = _sum(revenue_values)
    profit = _sum(profit_values)
    return {
        "bought_count": bought,
        "sold_count": sold,
        "cost": _sum(cost_values),
        "revenue": revenue,
        "profit": profit,
        "avg_profit": round(profit / sold, 2) if sold else None,
        "margin": round(profit / revenue * 100, 2) if revenue else None,
    }


def _trend(rows: List[Dict[str, Any]], money: Dict[int, Dict[str, Any]],
           start: dt.date, end: dt.date, granularity: str) -> List[Dict[str, Any]]:
    """按日（或按月）的成本 / 收入 / 利润 / 进出数量。

    先把区间里每个桶都建出来再填数：没有交易的日子必须占住一个 x 轴刻度，
    否则折线会把空档直接抹平，看上去像那几天一直有稳定收益。
    """
    buckets: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    cursor = start
    while cursor <= end:
        key = _bucket_key(cursor, granularity)
        if key not in buckets:
            buckets[key] = {"date": key, "cost": 0.0, "revenue": 0.0, "profit": 0.0,
                            "bought": 0, "sold": 0}
        cursor += dt.timedelta(days=1)

    for row in rows:
        m = money[row["id"]]
        purchase_date = row.get("purchase_date")
        sale_date = row.get("sale_date")
        if purchase_date and start <= purchase_date <= end:
            bucket = buckets[_bucket_key(purchase_date, granularity)]
            bucket["bought"] += 1
            if m["cost_total_cny"] is not None:
                bucket["cost"] = round(bucket["cost"] + m["cost_total_cny"], 2)
        if sale_date and start <= sale_date <= end and _is_sold(row):
            bucket = buckets[_bucket_key(sale_date, granularity)]
            bucket["sold"] += 1
            if m["sale_cny"] is not None:
                bucket["revenue"] = round(bucket["revenue"] + m["sale_cny"], 2)
            if m["profit_cny"] is not None:
                bucket["profit"] = round(bucket["profit"] + m["profit_cny"], 2)

    return list(buckets.values())


def _platforms(rows: List[Dict[str, Any]], money: Dict[int, Dict[str, Any]],
               start: dt.date, end: dt.date) -> List[Dict[str, Any]]:
    """平台对比：按**购入日落在区间内**的卡分组（来源平台是买入时的属性）。"""
    def _blank(name: str) -> Dict[str, Any]:
        return {"platform": name, "count": 0, "sold": 0,
                "cost": 0.0, "revenue": 0.0, "profit": 0.0}

    grouped: Dict[str, Dict[str, Any]] = {p: _blank(p) for p in SOURCE_PLATFORMS}
    for row in rows:
        purchase_date = row.get("purchase_date")
        if not purchase_date or not (start <= purchase_date <= end):
            continue
        key = row.get("source_platform") or "other"
        bucket = grouped.setdefault(key, _blank(key))
        m = money[row["id"]]
        bucket["count"] += 1
        if m["cost_total_cny"] is not None:
            bucket["cost"] = round(bucket["cost"] + m["cost_total_cny"], 2)
        if _is_sold(row):
            bucket["sold"] += 1
            for field, value in (("revenue", m["sale_cny"]), ("profit", m["profit_cny"])):
                if value is not None:
                    bucket[field] = round(bucket[field] + value, 2)
    return sorted((b for b in grouped.values() if b["count"]), key=lambda b: -b["cost"])


@router.get("/summary")
def summary(
    days: int = Query(default=30, ge=0, le=3650, description="最近 N 天；0 表示全部"),
    start: Optional[dt.date] = Query(default=None, description="显式区间起点，优先于 days"),
    end: Optional[dt.date] = Query(default=None),
):
    rows = db.query("SELECT * FROM cards WHERE is_draft = 0")  # 草稿不计入统计
    money = {row["id"]: cards.compute_money(row) for row in rows}

    today = dt.date.today()
    end_date = end or today
    if start:
        start_date = start
    elif days == 0:
        # 「全部」：起点取全库最早的交易日；一条日期都没有时退化成单日区间
        known = [d for row in rows for d in (row.get("purchase_date"), row.get("sale_date")) if d]
        start_date = min(known) if known else end_date
    else:
        start_date = end_date - dt.timedelta(days=days - 1)
    if start_date > end_date:
        start_date = end_date

    span = (end_date - start_date).days + 1
    prev_end = start_date - dt.timedelta(days=1)
    prev_start = prev_end - dt.timedelta(days=span - 1)
    granularity = "month" if span > _MONTH_BUCKET_DAYS else "day"

    # ── 全库口径（不随区间变）：库存健康度 / 状态构成 / 待处理都看全库 ──
    by_status: Dict[str, int] = {s: 0 for s in CARD_STATUSES}
    in_stock_by_status: Dict[str, int] = {}
    all_cost, all_revenue, all_profit, in_stock_cost = [], [], [], []
    sold_total = incomplete = 0
    for row in rows:
        m = money[row["id"]]
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        if m["incomplete"]:
            incomplete += 1
        all_cost.append(m["cost_total_cny"])
        if _is_sold(row):
            sold_total += 1
            all_revenue.append(m["sale_cny"])
            all_profit.append(m["profit_cny"])
        else:
            in_stock_by_status[row["status"]] = in_stock_by_status.get(row["status"], 0) + 1
            in_stock_cost.append(m["cost_total_cny"])

    total_revenue = _sum(all_revenue)
    total_profit = _sum(all_profit)

    return {
        "generated_at": int(time.time()),
        "range": {"start": start_date.isoformat(), "end": end_date.isoformat(), "days": span},
        "trend_granularity": granularity,
        "kpi": {
            "current": _period(rows, money, start_date, end_date),
            "previous": _period(rows, money, prev_start, prev_end),
            "today": _period(rows, money, today, today),
        },
        "trend": _trend(rows, money, start_date, end_date, granularity),
        "platforms": _platforms(rows, money, start_date, end_date),
        "stock": {
            "total_cards": len(rows),
            "sold_cards": sold_total,
            "in_stock_cards": len(rows) - sold_total,
            "in_stock_cost_cny": _sum(in_stock_cost),
            "total_cost_cny": _sum(all_cost),
            "total_revenue_cny": total_revenue,
            "total_profit_cny": total_profit,
            "avg_profit_cny": round(total_profit / sold_total, 2) if sold_total else None,
            "profit_margin": round(total_profit / total_revenue * 100, 2) if total_revenue else None,
            # 有多少张卡因为缺汇率算不出准确金额——这个数不是 0 的话，上面的合计就是偏低的，
            # 界面上必须显示出来，否则用户会把一个残缺的合计当成真实业绩。
            "incomplete_cards": incomplete,
            "by_status": by_status,
            "in_stock_by_status": in_stock_by_status,
        },
        "work": {
            **{s: by_status.get(s, 0) for s in _WORK_STATUSES},
            "incomplete": incomplete,
        },
    }


@router.get("/recent")
def recent(limit: int = Query(default=8, ge=1, le=50)):
    rows = db.query("SELECT * FROM cards WHERE is_draft = 0 ORDER BY created_at DESC, id DESC LIMIT %s", (limit,))
    media_map = cards.load_media([r["id"] for r in rows])
    return {"items": [cards.serialize(r, media_map.get(r["id"], [])) for r in rows]}


@router.get("/top-models")
def top_models(limit: int = Query(default=10, ge=1, le=50)):
    """按型号汇总数量和利润，看哪种卡最赚钱。"""
    rows = db.query("SELECT * FROM cards WHERE is_draft = 0 AND model IS NOT NULL AND model <> ''")
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = f"{row.get('brand') or ''} {row['model']}".strip()
        bucket = grouped.setdefault(key, {"model": key, "count": 0, "profit_cny": 0.0, "sold": 0})
        bucket["count"] += 1
        money = cards.compute_money(row)
        if money["profit_cny"] is not None:
            bucket["profit_cny"] = round(bucket["profit_cny"] + money["profit_cny"], 2)
            bucket["sold"] += 1
    items = sorted(grouped.values(), key=lambda x: (-x["count"], -x["profit_cny"]))
    return {"items": items[:limit]}
