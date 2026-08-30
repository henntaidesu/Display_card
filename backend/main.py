# -*- coding: utf-8 -*-
"""Display Card Manager 后端入口。

启动顺序：读 conf.ini → 建库建表 → 注册路由 → 挂前端。建表放在 lifespan 里而不是
模块顶层，是为了让 MySQL 没起来的时候错误信息出现在启动日志里，而不是变成一个
import 期的堆栈——那种报错完全指不出「是数据库连不上」。
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 冻结成 exe 后 sys.path 里没有 backend 目录，src.* 的导入会失败
if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(sys.executable)))
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import conf  # noqa: E402
from src.api import router as api_router  # noqa: E402
from src.web_static import mount_spa, register_health  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("displaycard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src import schema

    # conf.ini 不存在时自动生成一份不含注释的默认配置，让首次运行不至于连文件都没有。
    if conf.ensure_conf_file():
        log.warning("已生成默认 conf.ini：%s —— 请填写 [mysql] 的连接信息后重启", conf.conf_path())

    cfg = conf.mysql_config()
    log.info("配置文件：%s", conf.conf_path())
    log.info("MySQL：%s@%s:%s/%s", cfg["user"], cfg["host"], cfg["port"], cfg["database"])
    try:
        schema.init()
        log.info("数据库就绪")
    except Exception as exc:  # noqa: BLE001
        # 不在这里退出进程：/api/health 仍要能应答，前端才能显示一个像样的
        # 「数据库连不上」提示，而不是一个浏览器级的连接被拒绝页面。
        log.error("数据库初始化失败：%s", exc)
        log.error("请检查 conf.ini 的 [mysql] 配置，修好后访问 /api/v1/system/database/reconnect 重连")
    yield
    from src import db

    db.reset_pool()


_ENABLE_DOCS = (os.environ.get("DISPLAYCARD_ENABLE_DOCS") or "").strip().lower() in ("1", "true", "yes")

app = FastAPI(
    title="Display Card Manager",
    version="1.0.0",
    lifespan=lifespan,
    # /docs 默认关闭：局域网里它是一份未认证可读的完整路由与参数清单。
    # 需要时设 DISPLAYCARD_ENABLE_DOCS=1。
    docs_url="/docs" if _ENABLE_DOCS else None,
    redoc_url="/redoc" if _ENABLE_DOCS else None,
    openapi_url="/openapi.json" if _ENABLE_DOCS else None,
)

# 认证走 Authorization Bearer 而非 Cookie，所以默认允许任意来源但**关闭凭证**——
# 「通配 origin + allow_credentials」是明确危险的组合，这里从结构上避开它。
# 需要锁定来源时设 DISPLAYCARD_CORS_ORIGINS="https://host:9911"（逗号分隔）。
_cors_env = (os.environ.get("DISPLAYCARD_CORS_ORIGINS") or "").strip()
if _cors_env:
    _origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
    _allow_credentials = True
else:
    _origins = ["*"]
    _allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
register_health(app)
mount_spa(app)  # 必须最后挂：根路径兜底会吃掉其余未匹配路由


if __name__ == "__main__":
    from src.server import run

    # 传入 "main:app"：开启热重载时 uvicorn 需要这个导入串才能在改代码后重新加载。
    run(app, import_string="main:app")
