# -*- coding: utf-8 -*-
"""系统配置：图床连接、数据库状态、conf.ini 概况。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src import conf, db
from src.auth import require_admin, require_auth
from src.media import ImageHostingClient, ImageHostingError
from src.media import settings as media_settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


class ImageHostingPayload(BaseModel):
    base_url: Optional[str] = None
    public_base: Optional[str] = None
    project: Optional[str] = None
    # 留空 = 不修改已保存的 Token（前端永远拿不到 Token 原文，空值当清空会误删）
    token: Optional[str] = None
    timeout: Optional[int] = None
    verify_tls: Optional[bool] = None


@router.get("/image-hosting", dependencies=[Depends(require_auth)])
def get_image_hosting() -> Dict[str, Any]:
    config = media_settings.get_public()
    config["media_count"] = int(
        db.query_scalar("SELECT COUNT(*) AS c FROM card_media", default=0) or 0
    )
    return config


@router.put("/image-hosting", dependencies=[Depends(require_admin)])
def save_image_hosting(payload: ImageHostingPayload):
    media_settings.save(payload.model_dump(exclude_unset=True))
    return media_settings.get_public()


@router.post("/image-hosting/test", dependencies=[Depends(require_auth)])
def test_image_hosting():
    """用**已保存**的配置去 ping 图床，所以要先保存再测。

    顺带把图床侧的限制回给前端：允许的扩展名、单文件上限。上传组件用它来提前拦下
    传不上去的文件，而不是让用户等一次完整上传再收到拒绝。
    """
    try:
        result = ImageHostingClient().ping()
    except ImageHostingError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    return {
        "ok": True,
        "project": result.get("project"),
        "max_upload_bytes": result.get("max_upload_bytes"),
        "allowed_extensions": result.get("allowed_extensions"),
        "derivative_widths": result.get("derivative_widths"),
    }


@router.get("/database", dependencies=[Depends(require_admin)])
def database_status():
    """数据库连接状态。密码不回传，只回一个 password_set 布尔值。"""
    info = conf.describe()
    try:
        info.update(db.ping())
    except Exception as exc:  # noqa: BLE001
        info.update({"ok": False, "error": str(exc)})
    if info.get("ok"):
        info["tables"] = db.query(
            "SELECT TABLE_NAME AS name, TABLE_ROWS AS approx_rows "
            "FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() "
            "ORDER BY TABLE_NAME"
        )
    return info


@router.post("/database/reconnect", dependencies=[Depends(require_admin)])
def database_reconnect():
    """重读 conf.ini 并重建连接池。改完配置文件不用重启整个服务。"""
    db.reset_pool()
    try:
        return {"ok": True, **db.ping()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"重连失败：{exc}")
