# -*- coding: utf-8 -*-
"""口令散列与 JWT 签名密钥。"""

from __future__ import annotations

import os
import secrets

import bcrypt


def hash_password(plain: str) -> str:
    """bcrypt 散列。

    bcrypt 只看口令的**前 72 字节**，更长的部分被静默丢弃；这里显式截断，
    免得「超长口令的后半段其实没参与校验」变成一个看不见的行为。
    """
    raw = (plain or "").encode("utf-8")[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw((plain or "").encode("utf-8")[:72], hashed.encode("ascii"))
    except (ValueError, TypeError):
        # 库里存了非 bcrypt 格式的字符串（手工改过、迁移残留）时不抛，直接判失败
        return False


def get_or_create_jwt_secret() -> str:
    """JWT 签名密钥：环境变量优先，否则从 app_settings 取，没有就生成一个强随机的存进去。

    刻意不回退到源码里的常量——那等于把签名密钥公开，任何拿到源码的人都能伪造令牌。
    密钥存在 MySQL 里，重启后仍然有效，登录状态不会因为重启被清空。
    """
    env_secret = (os.environ.get("DISPLAYCARD_JWT_SECRET") or "").strip()
    if env_secret:
        return env_secret

    from src import settings_store

    secret = settings_store.get("jwt_secret")
    if secret:
        return secret
    secret = secrets.token_urlsafe(48)
    settings_store.set("jwt_secret", secret)
    return secret
