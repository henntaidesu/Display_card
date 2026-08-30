# -*- coding: utf-8 -*-
"""Uvicorn 启动。后端只监听普通 HTTP，需要 HTTPS 就在前面放 nginx。"""

from __future__ import annotations

import logging
import sys

import uvicorn
from fastapi import FastAPI

from src import conf

log = logging.getLogger(__name__)


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


def run(app: FastAPI) -> None:
    _enable_windows_console_ansi()
    cfg = conf.server_config()
    log.info("后端启动：http://%s:%s", cfg["host"], cfg["port"])
    uvicorn.run(
        app,
        host=cfg["host"],
        port=cfg["port"],
        log_level="info",
        # 前置 nginx 时要让后端认得 X-Forwarded-Proto / X-Forwarded-For，
        # 否则日志里的客户端 IP 全是 127.0.0.1。
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
    )
