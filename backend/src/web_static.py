# -*- coding: utf-8 -*-
"""托管打包后的前端，并提供健康检查。

开发时前端跑在 Vite dev server（9911）上，通过代理打到后端，这里挂不挂静态资源都无所谓；
打包成 exe 后前端 dist 被塞进同一个进程，由这里兜底。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.app_paths import project_root

log = logging.getLogger(__name__)


def _dist_dir() -> Path | None:
    """找前端产物。

    冻结态优先找 exe **同目录**下的 webside/dist —— 放一份在那里就能热替换前端，
    不必为了改一行文案重新打包整个 exe。找不到再回落到打进 exe 内部的那份
    （PyInstaller 解压到 sys._MEIPASS）。
    """
    candidates = [project_root() / "webside" / "dist"]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "webside" / "dist")
    for path in candidates:
        if (path / "index.html").exists():
            return path
    return None


def register_health(app: FastAPI) -> None:
    @app.get("/api/health", include_in_schema=False)
    def health():
        """前端断连遮罩靠轮询它来判断后端是否恢复，所以**必须不需要登录**，
        而且不能碰数据库——数据库挂了的时候恰恰最需要这个端点还能应答。"""
        return {"ok": True}

    @app.get("/api/health/db", include_in_schema=False)
    def health_db():
        from src import db

        try:
            return db.ping()
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(status_code=503, content={"ok": False, "error": str(exc)})


def mount_spa(app: FastAPI) -> None:
    """挂载单页应用。**必须最后调用**：根路径的兜底会吃掉所有未匹配的路由。"""
    dist = _dist_dir()
    if dist is None:
        log.info("未找到 webside/dist，跳过前端托管（开发模式下由 Vite 提供前端）")
        return

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    static_dir = dist / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    index_file = dist / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """前端用 hash 路由，理论上所有页面都是同一个 index.html。

        仍然要处理 full_path：favicon.ico、logo.svg 这类根目录下的实体文件要真的
        发出去，只有它们不存在时才回 index.html。
        """
        # 没匹配上的接口路径必须 404，绝不能回 index.html：那会让前端拿到一个
        # 200 + 一整页 HTML，当成正常响应去读字段，于是每个字段都是 undefined，
        # 页面以各种离奇的方式坏掉（分页器直接不渲染之类），而真正的原因
        # ——「这个接口不存在 / 后端还没重启」——一点线索都看不到。
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail=f"接口不存在：/{full_path}")
        candidate = (dist / full_path).resolve()
        # 必须做前缀校验：不然 ../../conf.ini 这样的路径能把 MySQL 密码读出去。
        if full_path and candidate.is_file() and str(candidate).startswith(str(dist.resolve())):
            return FileResponse(candidate)
        return FileResponse(index_file)

    log.info("前端已挂载：%s", dist)
