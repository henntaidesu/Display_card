# -*- coding: utf-8 -*-
"""JWT 鉴权依赖。结构与 FreeMarket_Manager 对齐，便于两套系统互相参照。"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src import db

JWT_ALGORITHM = "HS256"
# 0 = 永不过期（默认）：不写 exp 声明。失效由 token_version 控制——
# 改密码 / 禁用账号会自增 token_version，旧令牌立刻作废。
JWT_EXPIRE_HOURS = int(os.getenv("DISPLAYCARD_JWT_EXPIRE_HOURS", "0"))

_bearer = HTTPBearer(auto_error=False)

# 密钥要读库，而建表又发生在启动流程里，模块级求值会在导入期就打数据库。
# 延迟到第一次真正签发/校验令牌时再取，然后缓存。
_secret_cache: Optional[str] = None
_secret_lock = threading.Lock()


def _secret() -> str:
    global _secret_cache
    if _secret_cache is None:
        with _secret_lock:
            if _secret_cache is None:
                from src.security import get_or_create_jwt_secret

                _secret_cache = get_or_create_jwt_secret()
    return _secret_cache


def create_access_token(user_id: int, username: str, token_version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "tv": int(token_version or 0),
        "iat": int(now.timestamp()),
    }
    if JWT_EXPIRE_HOURS > 0:
        payload["exp"] = int((now + timedelta(hours=JWT_EXPIRE_HOURS)).timestamp())
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def verify_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的登录凭证")


def _load_auth_user(user_id: int) -> Optional[dict]:
    return db.query_one(
        "SELECT id, username, is_active, is_admin, token_version "
        "FROM users WHERE id = %s LIMIT 1",
        (user_id,),
    )


# 活跃时间写库节流：require_auth 每个请求都会走，逐请求 UPDATE 会把一个纯展示用的
# 字段变成全站最高频的写。60 秒一次足够——「刚刚在线」的判断不会因此失真。
_ACTIVE_TOUCH_INTERVAL_SEC = 60
_ACTIVE_TOUCH_LOCK = threading.Lock()
_ACTIVE_TOUCH_AT: dict = {}


def _touch_last_active(user_id: int) -> None:
    now = time.monotonic()
    with _ACTIVE_TOUCH_LOCK:
        last = _ACTIVE_TOUCH_AT.get(user_id)
        if last is not None and (now - last) < _ACTIVE_TOUCH_INTERVAL_SEC:
            return
        _ACTIVE_TOUCH_AT[user_id] = now
    try:
        db.execute("UPDATE users SET last_active_at = NOW() WHERE id = %s", (user_id,))
    except Exception:  # noqa: BLE001  刷新活跃时间失败绝不能影响鉴权本身
        with _ACTIVE_TOUCH_LOCK:
            _ACTIVE_TOUCH_AT.pop(user_id, None)


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    if not credentials or (credentials.scheme or "").lower() != "bearer":
        raise HTTPException(status_code=401, detail="未登录或令牌格式错误")
    claims = verify_access_token(credentials.credentials)
    try:
        uid = int(claims.get("sub") or 0)
    except (TypeError, ValueError):
        uid = 0
    user = _load_auth_user(uid) if uid > 0 else None
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或登录已失效")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    if int(claims.get("tv") or 0) != int(user["token_version"] or 0):
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    _touch_last_active(user["id"])
    claims["user_id"] = user["id"]
    claims["is_admin"] = 1 if user["is_admin"] else 0
    return claims


def require_admin(claims: dict = Depends(require_auth)) -> dict:
    if not claims.get("is_admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return claims
