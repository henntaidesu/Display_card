# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包规格：把后端 + 前端 dist 打成单个 exe。

前端 webside/dist 通过 datas 塞进 exe，运行时 web_static.py 会从 sys._MEIPASS 里读；
也支持在 exe 同目录放一个 webside/dist 来热替换前端而不重新打包。
"""

import os
from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.getcwd())
BACKEND = os.path.join(ROOT, "backend")
DIST_WEB = os.path.join(ROOT, "webside", "dist")

datas = []
if os.path.isdir(DIST_WEB):
    datas.append((DIST_WEB, os.path.join("webside", "dist")))

# uvicorn / pymysql 有大量运行时动态导入的子模块，收集全避免打包后缺模块
hidden = []
for pkg in ("uvicorn", "pymysql", "email", "anyio"):
    hidden += collect_submodules(pkg)
hidden += ["pymysql.cursors"]

a = Analysis(
    [os.path.join(BACKEND, "main.py")],
    pathex=[BACKEND],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "torch", "cv2"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DisplayCardManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 保留控制台窗口，方便看后端日志和数据库连接情况
    disable_windowed_traceback=False,
    icon=None,
)
