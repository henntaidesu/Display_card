# -*- coding: utf-8 -*-
"""Uvicorn 启动。后端只监听普通 HTTP，需要 HTTPS 就在前面放 nginx。"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

import uvicorn
from fastapi import FastAPI

from src import conf

log = logging.getLogger(__name__)


def _reload_enabled() -> bool:
    # 热重载只在开发时开：设 DISPLAYCARD_RELOAD=1（start.bat 会设）。打包成 exe 后
    # 冻结态不能用 reload（会重新 spawn 自身导致递归/找不到模块），所以冻结时强制关闭。
    if getattr(sys, "frozen", False):
        return False
    return (os.environ.get("DISPLAYCARD_RELOAD") or "").strip().lower() in ("1", "true", "yes")


def _enable_windows_console_ansi() -> None:
    """在 Windows 控制台开启 VT 处理，让 uvicorn 日志的颜色码正常渲染，
    而不是显示成 ``[32m...[0m`` 这样的乱码（打包成 exe 后在 CMD 里跑尤其明显）。
    只开 VT，不改代码页，避免影响中文输出。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        for handle_id in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except Exception:  # noqa: BLE001
        pass


def run(app: FastAPI, import_string: Optional[str] = None) -> None:
    """启动服务。

    ``import_string``（如 ``"main:app"``）只在开启热重载时用得上——uvicorn 的 reload
    必须拿一个「模块:变量」字符串才能在文件改动后重新导入应用；直接传 app 对象是没法
    reload 的。不重载时就用传进来的 app 对象，省一次导入。
    """
    _enable_windows_console_ansi()
    cfg = conf.server_config()
    reload = _reload_enabled() and bool(import_string)

    common = dict(
        host=cfg["host"],
        port=cfg["port"],
        log_level="info",
        # 前置 nginx 时要让后端认得 X-Forwarded-Proto / X-Forwarded-For，
        # 否则日志里的客户端 IP 全是 127.0.0.1。
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
    )

    if reload:
        log.info("后端启动（热重载已开启）：http://%s:%s", cfg["host"], cfg["port"])
        # 只监视 backend 目录下的 .py，改前端不触发后端重启（前端有 Vite 自己的 HMR）。
        from src.app_paths import backend_root

        uvicorn.run(
            import_string,
            reload=True,
            reload_dirs=[str(backend_root())],
            **common,
        )
    else:
        log.info("后端启动：http://%s:%s", cfg["host"], cfg["port"])
        uvicorn.run(app, **common)
