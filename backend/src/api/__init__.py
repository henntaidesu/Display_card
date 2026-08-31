# -*- coding: utf-8 -*-
"""API 路由汇总。

全部端点挂在 ``/api/v1`` 下。前端 axios 实例的 baseURL 也是它，各 api 模块只拼
``/cards``、``/media`` 这样的相对路径。
"""

from fastapi import APIRouter

from src.api import (
    auth_api,
    cards_api,
    dashboard_api,
    devices_api,
    funds_api,
    inventory_api,
    fx_api,
    media_api,
    options_api,
    system_api,
)

router = APIRouter(prefix="/api/v1")

router.include_router(auth_api.router)
router.include_router(cards_api.router)
router.include_router(devices_api.router)
router.include_router(inventory_api.router)
router.include_router(media_api.router)
router.include_router(fx_api.router)
router.include_router(funds_api.router)
router.include_router(options_api.router)
router.include_router(dashboard_api.router)
router.include_router(system_api.router)
