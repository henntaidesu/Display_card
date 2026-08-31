# -*- coding: utf-8 -*-
"""资金池：注资、扣款与分摊明细。

写操作（注资/扣款的增删改）之后一律 ``funds.rebuild()`` 再返回，让响应里的
summary 就是重算后的结果——否则前端刚存完看到的还是旧的余额，得再刷一次才对得上。
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from src import db, funds
from src.auth import require_auth
from src.schema import POOL_CURRENCY

log = logging.getLogger(__name__)

router = APIRouter(prefix="/funds", tags=["funds"], dependencies=[Depends(require_auth)])


class InjectionPayload(BaseModel):
    """一笔注资。金额恒为日元；汇率留空则按注资日自动取牌价。"""

    inject_date: dt.date
    amount: float = Field(gt=0)
    currency: str = POOL_CURRENCY
    # 手填汇率 = 实际换汇价（1 人民币 = ? 日元）。填了就以它为准，牌价只是个近似。
    fx_rate: Optional[float] = Field(default=None, gt=0)
    channel: Optional[str] = Field(default=None, max_length=64)
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, v: str) -> str:
        v = (v or POOL_CURRENCY).upper().strip()
        if v != POOL_CURRENCY:
            raise ValueError(f"资金池只接受 {POOL_CURRENCY}")
        return v


class DrawPayload(BaseModel):
    """手工记的池内支出（手续费、代购费…）。

    卡片与整机的购入价、国际运费**不走这里**——那两类由各自表单上的「从资金池扣除」
    开关自动同步，手工再记一笔就会重复扣钱。
    """

    draw_date: dt.date
    amount: float = Field(gt=0)
    note: Optional[str] = Field(default=None, max_length=500)


def _clean(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _state(warnings=None):
    """所有写操作的统一响应：重算后的总账 + 两张明细表 + 警告。"""
    result = funds.rebuild()
    return {
        "summary": funds.summary(),
        "injections": funds.list_injections(),
        "draws": funds.list_draws(),
        "warnings": list(warnings or []) + result["warnings"],
    }


@router.get("/summary")
def summary():
    return funds.summary()


@router.get("")
def overview():
    """页面首屏一次拿全：总账 + 注资列表 + 扣款列表。"""
    return {
        "summary": funds.summary(),
        "injections": funds.list_injections(),
        "draws": funds.list_draws(),
    }


@router.get("/injections")
def list_injections():
    return {"items": funds.list_injections()}


@router.post("/injections")
def create_injection(payload: InjectionPayload):
    fx = funds.resolve_injection_fx(payload.inject_date, payload.fx_rate)
    db.insert(
        "INSERT INTO fund_injections (inject_date, amount, currency, fx_rate, fx_date, "
        "fx_manual, channel, note) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (payload.inject_date, payload.amount, payload.currency, fx["fx_rate"], fx["fx_date"],
         fx["fx_manual"], _clean(payload.channel), _clean(payload.note)),
    )
    return _state(fx["warnings"])


@router.put("/injections/{injection_id}")
def update_injection(injection_id: int, payload: InjectionPayload):
    existing = db.query_one("SELECT id FROM fund_injections WHERE id = %s", (injection_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="注资记录不存在")
    fx = funds.resolve_injection_fx(payload.inject_date, payload.fx_rate)
    db.execute(
        "UPDATE fund_injections SET inject_date = %s, amount = %s, currency = %s, fx_rate = %s, "
        "fx_date = %s, fx_manual = %s, channel = %s, note = %s WHERE id = %s",
        (payload.inject_date, payload.amount, payload.currency, fx["fx_rate"], fx["fx_date"],
         fx["fx_manual"], _clean(payload.channel), _clean(payload.note), injection_id),
    )
    return _state(fx["warnings"])


@router.delete("/injections/{injection_id}")
def delete_injection(injection_id: int):
    """删掉一批注资。

    已经被花掉的那部分不会阻止删除——分摊是派生数据，删完重算即可；只是原本吃这批钱
    的扣款会转而去吃别的批次，吃不到的部分变成「余额不足」并给出警告。这比禁止删除
    更实用：录错一笔注资是常事，而它往往已经被后面的扣款「用掉」了。
    """
    existing = db.query_one("SELECT id FROM fund_injections WHERE id = %s", (injection_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="注资记录不存在")
    db.execute("DELETE FROM fund_injections WHERE id = %s", (injection_id,))
    return _state()


@router.get("/draws")
def list_draws(
    card_id: Optional[int] = Query(default=None),
    device_id: Optional[int] = Query(default=None),
    limit: int = Query(default=300, ge=1, le=1000),
):
    return {"items": funds.list_draws(card_id=card_id, device_id=device_id, limit=limit)}


@router.post("/draws")
def create_draw(payload: DrawPayload):
    db.insert(
        "INSERT INTO fund_draws (card_id, device_id, category, draw_date, amount, currency, note) "
        "VALUES (NULL, NULL, 'other', %s, %s, %s, %s)",
        (payload.draw_date, payload.amount, POOL_CURRENCY, _clean(payload.note)),
    )
    return _state()


@router.put("/draws/{draw_id}")
def update_draw(draw_id: int, payload: DrawPayload):
    existing = db.query_one(
        "SELECT id, category, card_id, device_id FROM fund_draws WHERE id = %s", (draw_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="扣款记录不存在")
    if existing["card_id"] or existing["device_id"]:
        raise HTTPException(
            status_code=400,
            detail="这笔扣款跟着显卡 / 整机走，请到对应的那条记录上修改金额或关闭「从资金池扣除」。",
        )
    db.execute(
        "UPDATE fund_draws SET draw_date = %s, amount = %s, note = %s WHERE id = %s",
        (payload.draw_date, payload.amount, _clean(payload.note), draw_id),
    )
    return _state()


@router.delete("/draws/{draw_id}")
def delete_draw(draw_id: int):
    existing = db.query_one(
        "SELECT id, card_id, device_id FROM fund_draws WHERE id = %s", (draw_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="扣款记录不存在")
    if existing["card_id"] or existing["device_id"]:
        raise HTTPException(
            status_code=400,
            detail="这笔扣款跟着显卡 / 整机走，请到对应的那条记录上关闭「从资金池扣除」。",
        )
    db.execute("DELETE FROM fund_draws WHERE id = %s", (draw_id,))
    return _state()


@router.post("/rebuild")
def rebuild():
    """手工触发全量重算。补录了历史注资、或改过汇率后用它把成本刷一遍。"""
    return _state()
