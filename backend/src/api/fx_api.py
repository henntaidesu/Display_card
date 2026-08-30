# -*- coding: utf-8 -*-
"""汇率查询与缓存管理。"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src import db, settings_store
from src.auth import require_auth
from src.fx import FxError, get_rate, refresh_range
from src.fx.providers import PROVIDERS

router = APIRouter(prefix="/fx", tags=["fx"], dependencies=[Depends(require_auth)])


@router.get("/rate")
def rate(
    date: Optional[dt.date] = Query(default=None, description="留空取今天"),
    base: str = Query(default="CNY"),
    quote: str = Query(default="JPY"),
):
    """取某天的汇率。录卡时选完日期就调它，让用户在保存前先看到会用哪个汇率。"""
    try:
        result = get_rate(date or dt.date.today(), base.upper(), quote.upper())
    except FxError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {
        "rate": result["rate"],
        "rate_date": result["rate_date"].isoformat(),
        "requested_date": (date or dt.date.today()).isoformat(),
        "source": result["source"],
        "stale": result["stale"],
        "base": base.upper(),
        "quote": quote.upper(),
    }


@router.get("/history")
def history(
    start: dt.date = Query(...),
    end: dt.date = Query(...),
    base: str = Query(default="CNY"),
    quote: str = Query(default="JPY"),
):
    """读缓存里的一段汇率，用于概览页画走势线。**只读本地，不打网络**——
    画个图不该触发几十次外部请求；缺的部分由 /fx/refresh 显式补。"""
    if start > end:
        start, end = end, start
    rows = db.query(
        "SELECT rate_date, rate, source FROM fx_rates "
        "WHERE rate_date BETWEEN %s AND %s AND base = %s AND quote = %s "
        "ORDER BY rate_date",
        (start, end, base.upper(), quote.upper()),
    )
    return {
        "items": [
            {"date": r["rate_date"].isoformat(), "rate": float(r["rate"]), "source": r["source"]}
            for r in rows
        ]
    }


@router.post("/refresh")
def refresh(
    start: Optional[dt.date] = Query(default=None),
    end: Optional[dt.date] = Query(default=None),
    days: int = Query(default=90, ge=1, le=3650),
):
    """批量补齐缓存。不给日期就补最近 ``days`` 天。一次区间请求，不是 N 次单日请求。"""
    end = end or dt.date.today()
    start = start or (end - dt.timedelta(days=days))
    try:
        count = refresh_range(start, end)
    except FxError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"ok": True, "cached": count, "start": start.isoformat(), "end": end.isoformat()}


@router.get("/config")
def get_config():
    return {
        "source": (settings_store.get("fx_source") or "ecb"),
        "auto_fetch": settings_store.get_bool("fx_auto_fetch", default=True),
        "available": [
            {"key": key, "label": cls.label} for key, cls in PROVIDERS.items()
        ],
        "cached_count": int(db.query_scalar("SELECT COUNT(*) AS c FROM fx_rates", default=0) or 0),
        "cached_range": db.query_one(
            "SELECT MIN(rate_date) AS min_date, MAX(rate_date) AS max_date FROM fx_rates"
        ),
    }


@router.put("/config")
def set_config(source: Optional[str] = Query(default=None), auto_fetch: Optional[bool] = Query(default=None)):
    if source is not None:
        if source not in PROVIDERS:
            raise HTTPException(status_code=400, detail=f"未知汇率源：{source}")
        settings_store.set("fx_source", source)
    if auto_fetch is not None:
        settings_store.set("fx_auto_fetch", auto_fetch)
    return get_config()
