# -*- coding: utf-8 -*-
"""显卡的增删改查、状态流转、汇率刷新。"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from src import cards, db
from src.auth import require_auth
from src.schema import CARD_STATUSES, CURRENCIES, SOURCE_PLATFORMS

log = logging.getLogger(__name__)

router = APIRouter(prefix="/cards", tags=["cards"], dependencies=[Depends(require_auth)])

# 允许写入的列 → 是否需要额外校验。顺序即 UPDATE 语句里的顺序。
_WRITABLE = [
    "brand", "model", "vram", "serial_no",
    "source_platform", "seller", "item_url", "order_no",
    "purchase_date", "purchase_amount", "purchase_currency",
    "intl_shipping_amount", "intl_shipping_currency",
    "domestic_shipping_amount", "domestic_shipping_currency",
    "sale_date", "sale_amount", "sale_currency",
    "status", "note",
]


class CardPayload(BaseModel):
    """新增/编辑的请求体。所有字段可选——录卡是渐进的，买的时候只知道价格，
    测完才有序列号，卖掉才有售价，不该强制一次填全。"""

    brand: Optional[str] = Field(default=None, max_length=64)
    model: Optional[str] = Field(default=None, max_length=128)
    vram: Optional[str] = Field(default=None, max_length=32)
    serial_no: Optional[str] = Field(default=None, max_length=128)

    source_platform: Optional[str] = Field(default=None, max_length=16)
    seller: Optional[str] = Field(default=None, max_length=128)
    item_url: Optional[str] = Field(default=None, max_length=1024)
    order_no: Optional[str] = Field(default=None, max_length=128)

    purchase_date: Optional[dt.date] = None
    purchase_amount: Optional[float] = Field(default=None, ge=0)
    purchase_currency: str = "JPY"
    intl_shipping_amount: Optional[float] = Field(default=None, ge=0)
    intl_shipping_currency: str = "JPY"
    domestic_shipping_amount: Optional[float] = Field(default=None, ge=0)
    domestic_shipping_currency: str = "CNY"
    sale_date: Optional[dt.date] = None
    sale_amount: Optional[float] = Field(default=None, ge=0)
    sale_currency: str = "CNY"

    status: str = "purchased"
    note: Optional[str] = None

    # 手工指定汇率：填了就用它，并置 fx_manual=1，之后自动刷新不再覆盖。
    purchase_fx_rate: Optional[float] = Field(default=None, gt=0)
    sale_fx_rate: Optional[float] = Field(default=None, gt=0)

    @field_validator("purchase_currency", "intl_shipping_currency",
                     "domestic_shipping_currency", "sale_currency")
    @classmethod
    def _check_currency(cls, v: str) -> str:
        v = (v or "").upper().strip()
        if v not in CURRENCIES:
            raise ValueError(f"币种只能是 {' / '.join(CURRENCIES)}")
        return v

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        v = (v or "purchased").strip()
        if v not in CARD_STATUSES:
            raise ValueError(f"未知状态：{v}")
        return v

    @field_validator("source_platform")
    @classmethod
    def _check_platform(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip().lower()
        if v not in SOURCE_PLATFORMS:
            raise ValueError(f"购买平台只能是 {' / '.join(SOURCE_PLATFORMS)}")
        return v


class StatusPayload(BaseModel):
    status: str
    note: Optional[str] = Field(default=None, max_length=500)


def _clean(value: Any) -> Any:
    """空字符串统一存成 NULL。

    不这么做的话，「没填」会以两种形态存在库里（'' 和 NULL），之后每个查询都要写
    ``WHERE seller IS NOT NULL AND seller <> ''`` 才对，漏一个就出错。
    """
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _apply_fx(payload: CardPayload) -> Dict[str, Any]:
    """决定这张卡用什么汇率：手填优先，否则按日期自动取。"""
    manual = payload.purchase_fx_rate is not None or payload.sale_fx_rate is not None
    resolved = cards.resolve_fx(payload.purchase_date, payload.sale_date)
    warnings: List[str] = list(resolved["warnings"])

    purchase_rate = payload.purchase_fx_rate or resolved["purchase_fx_rate"]
    sale_rate = payload.sale_fx_rate or resolved["sale_fx_rate"]
    # 手填汇率没有「牌价日」可言，就用交易日本身，界面上不至于显示成空。
    purchase_fx_date = (payload.purchase_date if payload.purchase_fx_rate
                        else resolved["purchase_fx_date"])
    sale_fx_date = payload.sale_date if payload.sale_fx_rate else resolved["sale_fx_date"]

    return {
        "purchase_fx_rate": purchase_rate,
        "purchase_fx_date": purchase_fx_date,
        "sale_fx_rate": sale_rate,
        "sale_fx_date": sale_fx_date,
        "fx_manual": 1 if manual else 0,
        "warnings": warnings,
    }


@router.get("")
def list_cards(
    keyword: Optional[str] = Query(default=None, description="型号/品牌/序列号/编号/卖家 模糊匹配"),
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
    where: List[str] = []
    params: List[Any] = []

    if keyword:
        like = f"%{keyword.strip()}%"
        where.append(
            "(mgmt_no LIKE %s OR brand LIKE %s OR model LIKE %s "
            "OR serial_no LIKE %s OR seller LIKE %s OR order_no LIKE %s)"
        )
        params.extend([like] * 6)
    if status:
        # 支持 ?status=a,b,c 多选筛选
        values = [s.strip() for s in status.split(",") if s.strip() in CARD_STATUSES]
        if values:
            where.append(f"status IN ({', '.join(['%s'] * len(values))})")
            params.extend(values)
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

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    # 排序列走白名单。直接把 sort_by 拼进 SQL 是注入口子，而 ORDER BY 又没法用占位符。
    sort_whitelist = {
        "created_at", "updated_at", "purchase_date", "sale_date",
        "mgmt_no", "brand", "model", "purchase_amount", "sale_amount", "status",
    }
    order_col = sort_by if sort_by in sort_whitelist else "created_at"
    order_dir = "ASC" if str(sort_dir).lower() == "asc" else "DESC"

    total = int(db.query_scalar(f"SELECT COUNT(*) AS c FROM cards{where_sql}", params, default=0) or 0)
    rows = db.query(
        f"SELECT * FROM cards{where_sql} ORDER BY {order_col} {order_dir}, id DESC "
        f"LIMIT %s OFFSET %s",
        params + [page_size, (page - 1) * page_size],
    )
    media_map = cards.load_media([r["id"] for r in rows])
    items = [cards.serialize(r, media_map.get(r["id"], [])) for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/next-mgmt-no")
def next_mgmt_no():
    """新建表单打开时预填一个编号。仅供展示，真正的编号在保存那一刻才生成。"""
    return {"mgmt_no": cards.next_mgmt_no()}


@router.get("/{card_id}")
def get_card(card_id: int):
    row = db.query_one("SELECT * FROM cards WHERE id = %s", (card_id,))
    if not row:
        raise HTTPException(status_code=404, detail="显卡不存在")
    media = cards.load_media([card_id]).get(card_id, [])
    data = cards.serialize(row, media)
    data["status_logs"] = [
        {
            "from_status": log_row["from_status"],
            "to_status": log_row["to_status"],
            "note": log_row["note"],
            "occurred_at": log_row["occurred_at"].isoformat() if log_row["occurred_at"] else None,
        }
        for log_row in db.query(
            "SELECT from_status, to_status, note, occurred_at FROM card_status_logs "
            "WHERE card_id = %s ORDER BY occurred_at, id",
            (card_id,),
        )
    ]
    return data


@router.post("")
def create_card(payload: CardPayload):
    fx = _apply_fx(payload)
    values = {name: _clean(getattr(payload, name)) for name in _WRITABLE}
    values["mgmt_no"] = cards.next_mgmt_no()
    values.update({k: fx[k] for k in
                   ("purchase_fx_rate", "purchase_fx_date", "sale_fx_rate", "sale_fx_date", "fx_manual")})

    columns = list(values.keys())
    card_id = db.insert(
        "INSERT INTO cards ({cols}) VALUES ({ph})".format(
            cols=", ".join(f"`{c}`" for c in columns),
            ph=", ".join(["%s"] * len(columns)),
        ),
        [values[c] for c in columns],
    )
    cards.log_status(card_id, None, values["status"], "创建")
    row = db.query_one("SELECT * FROM cards WHERE id = %s", (card_id,))
    result = cards.serialize(row, [])
    result["warnings"] = fx["warnings"]
    return result


@router.put("/{card_id}")
def update_card(card_id: int, payload: CardPayload):
    existing = db.query_one("SELECT * FROM cards WHERE id = %s", (card_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="显卡不存在")

    fx = _apply_fx(payload)
    values = {name: _clean(getattr(payload, name)) for name in _WRITABLE}
    values.update({k: fx[k] for k in
                   ("purchase_fx_rate", "purchase_fx_date", "sale_fx_rate", "sale_fx_date", "fx_manual")})

    db.execute(
        "UPDATE cards SET {sets} WHERE id = %s".format(
            sets=", ".join(f"`{c}` = %s" for c in values)
        ),
        list(values.values()) + [card_id],
    )
    cards.log_status(card_id, existing["status"], values["status"], "编辑")
    row = db.query_one("SELECT * FROM cards WHERE id = %s", (card_id,))
    media = cards.load_media([card_id]).get(card_id, [])
    result = cards.serialize(row, media)
    result["warnings"] = fx["warnings"]
    return result


@router.patch("/{card_id}/status")
def change_status(card_id: int, payload: StatusPayload):
    """只改状态。列表页的快捷操作走这里，不需要提交整个表单。"""
    try:
        status = cards.validate_status(payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    existing = db.query_one("SELECT id, status FROM cards WHERE id = %s", (card_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="显卡不存在")
    db.execute("UPDATE cards SET status = %s WHERE id = %s", (status, card_id))
    cards.log_status(card_id, existing["status"], status, payload.note or "")
    return {"ok": True, "status": status}


@router.post("/{card_id}/refresh-fx")
def refresh_fx(card_id: int):
    """按当前的买入/卖出日期重新取汇率。

    手工改过汇率的卡（fx_manual=1）会被拒绝——自动刷新把用户特意填的成交汇率冲掉，
    是那种发生了也不会有人立刻发现的破坏。要刷新就先显式清掉手工标记。
    """
    row = db.query_one("SELECT * FROM cards WHERE id = %s", (card_id,))
    if not row:
        raise HTTPException(status_code=404, detail="显卡不存在")
    if row["fx_manual"]:
        raise HTTPException(
            status_code=400,
            detail="这张卡的汇率是手工填写的，自动刷新会覆盖它。如需刷新请先在编辑页清空手填汇率。",
        )
    resolved = cards.resolve_fx(row["purchase_date"], row["sale_date"])
    db.execute(
        "UPDATE cards SET purchase_fx_rate = %s, purchase_fx_date = %s, "
        "sale_fx_rate = %s, sale_fx_date = %s WHERE id = %s",
        (resolved["purchase_fx_rate"], resolved["purchase_fx_date"],
         resolved["sale_fx_rate"], resolved["sale_fx_date"], card_id),
    )
    updated = db.query_one("SELECT * FROM cards WHERE id = %s", (card_id,))
    result = cards.serialize(updated, [])
    result["warnings"] = resolved["warnings"]
    return result


@router.delete("/{card_id}")
def delete_card(card_id: int, purge_media: bool = Query(default=False)):
    """删卡。

    ``purge_media=true`` 时连图床上的文件一起删。默认不删：图床是共享的，误删一张卡
    就永久丢掉几十张照片，代价太大；而留在图床上的孤儿文件只是占点空间。
    card_media 行由外键 ON DELETE CASCADE 自动清掉。
    """
    row = db.query_one("SELECT id FROM cards WHERE id = %s", (card_id,))
    if not row:
        raise HTTPException(status_code=404, detail="显卡不存在")

    purged, failed = 0, 0
    if purge_media:
        from src.media import ImageHostingClient, ImageHostingError

        stored = [m["stored_name"] for m in
                  db.query("SELECT stored_name FROM card_media WHERE card_id = %s", (card_id,))]
        if stored:
            try:
                client = ImageHostingClient()
            except ImageHostingError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            for name in stored:
                try:
                    client.delete(name)
                    purged += 1
                except ImageHostingError as exc:
                    # 单个文件删不掉不该阻断整次删除——记下来继续，卡片行还是要删的
                    log.warning("删除图床文件 %s 失败：%s", name, exc)
                    failed += 1

    db.execute("DELETE FROM cards WHERE id = %s", (card_id,))
    return {"ok": True, "media_purged": purged, "media_failed": failed}
