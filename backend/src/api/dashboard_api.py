# -*- coding: utf-8 -*-
"""概览页统计。

所有金额统计都在 **Python 侧**用 cards.compute_money 算，而不是写成一条 SQL 的
SUM。因为「金额 × 该行自己的汇率快照，且缺汇率时不当 0」这套规则在 SQL 里要写成
一坨 CASE WHEN，还会和 cards.py 里的规则各自演化——两处算出来的利润对不上时，
没人说得清哪个是对的。数据量是几百到几千行，一次全读回来毫无压力。
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from src import cards, db
from src.auth import require_auth
from src.cards import SOLD_STATUSES
from src.schema import CARD_STATUSES

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_auth)])


def _sum(values: List[Any]) -> float:
    return round(sum(v for v in values if v is not None), 2)


@router.get("/summary")
def summary(
    start: dt.date | None = Query(default=None, description="按购入日期过滤，留空统计全部"),
    end: dt.date | None = Query(default=None),
):
    where, params = [], []
    if start:
        where.append("purchase_date >= %s")
        params.append(start)
    if end:
        where.append("purchase_date <= %s")
        params.append(end)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    rows = db.query(f"SELECT * FROM cards{where_sql}", params)

    by_status: Dict[str, int] = {s: 0 for s in CARD_STATUSES}
    cost_values, revenue_values, profit_values = [], [], []
    sold_count = 0
    incomplete_count = 0
    monthly: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"cost": 0.0, "revenue": 0.0, "profit": 0.0, "count": 0}
    )

    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        money = cards.compute_money(row)
        if money["incomplete"]:
            incomplete_count += 1

        cost_values.append(money["cost_total_cny"])
        if row["status"] in SOLD_STATUSES or row.get("sale_amount") is not None:
            sold_count += 1
            revenue_values.append(money["sale_cny"])
            profit_values.append(money["profit_cny"])

        # 利润归到**卖出**那个月：这笔钱是那个月赚的，不是买卡那个月
        bucket_date = row.get("sale_date") or row.get("purchase_date")
        if bucket_date:
            key = bucket_date.strftime("%Y-%m")
            bucket = monthly[key]
            bucket["count"] += 1
            for field, value in (("cost", money["cost_total_cny"]),
                                 ("revenue", money["sale_cny"]),
                                 ("profit", money["profit_cny"])):
                if value is not None:
                    bucket[field] = round(bucket[field] + value, 2)

    total_revenue = _sum(revenue_values)
    total_profit = _sum(profit_values)

    return {
        "total_cards": len(rows),
        "sold_cards": sold_count,
        "in_stock_cards": len(rows) - sold_count,
        "by_status": by_status,
        "total_cost_cny": _sum(cost_values),
        "total_revenue_cny": total_revenue,
        "total_profit_cny": total_profit,
        "avg_profit_cny": round(total_profit / sold_count, 2) if sold_count else None,
        "profit_margin": round(total_profit / total_revenue * 100, 2) if total_revenue else None,
        # 有多少张卡因为缺汇率算不出准确金额——这个数不是 0 的话，上面的合计就是偏低的，
        # 界面上必须显示出来，否则用户会把一个残缺的合计当成真实业绩。
        "incomplete_cards": incomplete_count,
        "monthly": [
            {"month": month, **values}
            for month, values in sorted(monthly.items())
        ],
    }


@router.get("/recent")
def recent(limit: int = Query(default=8, ge=1, le=50)):
    rows = db.query("SELECT * FROM cards ORDER BY created_at DESC, id DESC LIMIT %s", (limit,))
    media_map = cards.load_media([r["id"] for r in rows])
    return {"items": [cards.serialize(r, media_map.get(r["id"], [])) for r in rows]}


@router.get("/top-models")
def top_models(limit: int = Query(default=10, ge=1, le=50)):
    """按型号汇总数量和利润，看哪种卡最赚钱。"""
    rows = db.query("SELECT * FROM cards WHERE model IS NOT NULL AND model <> ''")
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
