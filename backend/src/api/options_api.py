# -*- coding: utf-8 -*-
"""枚举与字典：状态、分类、币种、品牌、型号。

枚举的中日英三套文案在**前端** i18n 里，后端只发 key。理由：加一门语言不该需要
改后端并重启；而后端发中文、前端再翻译，等于同一份文案维护两遍。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src import db
from src.auth import require_auth
from src.schema import (
    CARD_STATUSES,
    CURRENCIES,
    DEVICE_PART_TYPES,
    FUND_DRAW_CATEGORIES,
    FUND_SOURCES,
    MEDIA_CATEGORIES,
    POOL_CURRENCY,
    SOURCE_PLATFORMS,
)

router = APIRouter(prefix="/options", tags=["options"], dependencies=[Depends(require_auth)])


class BrandPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    sort_order: int = 0


class ModelPayload(BaseModel):
    # 型号独立于品牌，只有名字（如 RTX 4090）和默认显存
    name: str = Field(min_length=1, max_length=128)
    default_vram: Optional[str] = Field(default=None, max_length=32)
    sort_order: int = 0


@router.get("/enums")
def enums():
    return {
        "statuses": CARD_STATUSES,
        "media_categories": MEDIA_CATEGORIES,
        "device_part_types": DEVICE_PART_TYPES,
        "source_platforms": SOURCE_PLATFORMS,
        "currencies": CURRENCIES,
        "fund_sources": FUND_SOURCES,
        "fund_draw_categories": FUND_DRAW_CATEGORIES,
        "pool_currency": POOL_CURRENCY,
    }


@router.get("/brands")
def list_brands():
    return {
        "items": db.query(
            "SELECT id, name, sort_order FROM gpu_brands ORDER BY sort_order, name"
        )
    }


@router.post("/brands")
def create_brand(payload: BrandPayload):
    name = payload.name.strip()
    existing = db.query_one("SELECT id, name, sort_order FROM gpu_brands WHERE name = %s", (name,))
    if existing:
        # 录卡时在下拉里现敲一个已存在的品牌不该报错——直接把已有的那条还回去，
        # 前端选中它就行，用户根本不需要知道刚才发生过一次重复。
        return existing
    brand_id = db.insert(
        "INSERT INTO gpu_brands (name, sort_order) VALUES (%s, %s)", (name, payload.sort_order)
    )
    return {"id": brand_id, "name": name, "sort_order": payload.sort_order}


@router.delete("/brands/{brand_id}")
def delete_brand(brand_id: int):
    db.execute("DELETE FROM gpu_brands WHERE id = %s", (brand_id,))
    return {"ok": True}


@router.get("/models")
def list_models():
    """所有型号，独立于品牌。列表和录卡下拉都用这一份完整清单。"""
    return {
        "items": db.query(
            "SELECT id, name, default_vram, sort_order FROM gpu_models "
            "ORDER BY sort_order, name"
        )
    }


@router.post("/models")
def create_model(payload: ModelPayload):
    name = payload.name.strip()
    existing = db.query_one(
        "SELECT id, name, default_vram, sort_order FROM gpu_models WHERE name = %s",
        (name,),
    )
    if existing:
        # 录卡时现敲一个已存在的型号不该报错，直接把已有那条还回去
        return existing
    model_id = db.insert(
        "INSERT INTO gpu_models (name, default_vram, sort_order) VALUES (%s, %s, %s)",
        (name, (payload.default_vram or "").strip() or None, payload.sort_order),
    )
    return {
        "id": model_id, "name": name,
        "default_vram": payload.default_vram, "sort_order": payload.sort_order,
    }


@router.delete("/models/{model_id}")
def delete_model(model_id: int):
    db.execute("DELETE FROM gpu_models WHERE id = %s", (model_id,))
    return {"ok": True}


@router.get("/used-brands")
def used_brands():
    """卡片表里**实际出现过**的品牌，给列表页的筛选下拉用。

    和 /brands 的区别：那个是可选清单（含还没买过的品牌），这个是已有数据。
    筛选下拉里列一堆筛出来必定为空的选项，只会让人以为系统坏了。
    """
    rows = db.query(
        "SELECT brand, COUNT(*) AS count FROM cards "
        "WHERE brand IS NOT NULL AND brand <> '' GROUP BY brand ORDER BY count DESC, brand"
    )
    return {"items": rows}
