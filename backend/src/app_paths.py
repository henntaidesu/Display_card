# -*- coding: utf-8 -*-
"""开发态与 PyInstaller 冻结态下的项目根目录。

冻结后 exe 同目录即为根：conf.ini、data/ 都跟着 exe 走，换台机器只要带上这两样。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def project_root() -> Path:
    override = (os.environ.get("DISPLAYCARD_ROOT") or "").strip()
    if override:
        return Path(override).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # backend/src/app_paths.py → backend/ → 项目根
    return Path(__file__).resolve().parents[2]


def backend_root() -> Path:
    """开发态是 backend/；冻结态没有 backend 这一层，与 exe 同目录。"""
    if getattr(sys, "frozen", False):
        return project_root()
    return Path(__file__).resolve().parents[1]


def conf_path() -> Path:
    """conf.ini 的位置。

    先看项目根（开发态是 Display_card/conf.ini，冻结态是 exe 同目录），
    找不到再看 backend/ —— 有人习惯把配置放在后端目录里，两边都认。
    """
    override = (os.environ.get("DISPLAYCARD_CONF") or "").strip()
    if override:
        return Path(override).resolve()
    root_conf = project_root() / "conf.ini"
    if root_conf.exists():
        return root_conf
    backend_conf = backend_root() / "conf.ini"
    if backend_conf.exists():
        return backend_conf
    return root_conf


def data_dir() -> Path:
    d = backend_root() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d
