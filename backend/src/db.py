# -*- coding: utf-8 -*-
"""MySQL 访问层（PyMySQL 原生，无 ORM）。

自带一个极简连接池。不用 SQLAlchemy 是刻意的：这个系统的查询都是手写 SQL，
引入 ORM 只会在「原生 MySQL」和「Python 对象」之间多垫一层需要维护的映射。

三个约定：
1. **所有 SQL 用 %s 占位符**，永远不要用 f-string 拼接用户输入。
2. 写操作走 ``execute`` / ``executemany``，读操作走 ``query`` / ``query_one``，
   两者都会自己借还连接，调用方不需要关心事务边界；需要跨多条语句的原子操作用
   ``transaction()`` 上下文管理器。
3. 连接借出时先 ``ping(reconnect=True)``。MySQL 的 wait_timeout 会静默掐掉空闲连接，
   池里留着的是个已死的 socket，不 ping 的话第一个请求必然报 "server has gone away"。
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from queue import Empty, LifoQueue
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pymysql
from pymysql.cursors import DictCursor

from src import conf

log = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    """数据库不可用或语句执行失败。上层转成 HTTP 500 / 503。"""


class _Pool:
    """LIFO 连接池。

    用 LIFO 而不是 FIFO：后进先出让最近用过的连接优先被复用，空闲连接自然沉底并很快
    超过 pool_recycle 被丢弃，池子在低负载时会自己收缩，而不是把 N 条连接全都吊着。
    """

    def __init__(self) -> None:
        self._cfg = conf.mysql_config()
        self._idle: LifoQueue = LifoQueue(maxsize=self._cfg["pool_size"])
        self._lock = threading.Lock()
        self._created = 0
        self._recycle = self._cfg["pool_recycle"]

    def _connect(self) -> pymysql.connections.Connection:
        cfg = self._cfg
        return pymysql.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            charset=cfg["charset"],
            cursorclass=DictCursor,
            autocommit=True,
            connect_timeout=10,
            read_timeout=30,
            write_timeout=30,
        )

    def acquire(self):
        while True:
            try:
                conn, born = self._idle.get_nowait()
            except Empty:
                break
            if time.monotonic() - born > self._recycle:
                _silent_close(conn)
                with self._lock:
                    self._created -= 1
                continue
            try:
                conn.ping(reconnect=True)
                return conn, born
            except Exception:  # noqa: BLE001  连接已死，丢掉再拿下一条
                _silent_close(conn)
                with self._lock:
                    self._created -= 1
                continue
        with self._lock:
            self._created += 1
        try:
            return self._connect(), time.monotonic()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._created -= 1
            raise DatabaseError(
                f"无法连接 MySQL（{self._cfg['host']}:{self._cfg['port']}）：{exc}"
            ) from exc

    def release(self, conn, born, broken: bool = False) -> None:
        if broken:
            _silent_close(conn)
            with self._lock:
                self._created -= 1
            return
        try:
            self._idle.put_nowait((conn, born))
        except Exception:  # noqa: BLE001  池满，多出来的连接直接关掉
            _silent_close(conn)
            with self._lock:
                self._created -= 1

    def close_all(self) -> None:
        while True:
            try:
                conn, _ = self._idle.get_nowait()
            except Empty:
                return
            _silent_close(conn)


def _silent_close(conn) -> None:
    try:
        conn.close()
    except Exception:  # noqa: BLE001
        pass


_pool: Optional[_Pool] = None
_pool_lock = threading.Lock()


def pool() -> _Pool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = _Pool()
    return _pool


def reset_pool() -> None:
    """改过 conf.ini 后重建连接池。旧连接直接关掉，不等它们自然过期。"""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close_all()
        _pool = None
    conf.load(refresh=True)


@contextmanager
def connection():
    """借一条连接，异常时把它标记为损坏并丢弃（避免把半死的连接还回池里）。"""
    conn, born = pool().acquire()
    broken = False
    try:
        yield conn
    except pymysql.err.Error:
        broken = True
        raise
    finally:
        pool().release(conn, born, broken=broken)


@contextmanager
def transaction():
    """把多条语句包成一个事务。

    连接默认 autocommit=True，这里临时关掉，块内全部成功才 commit。用于「插卡片 +
    插图片 + 写状态日志」这类必须同生共死的写入。
    """
    with connection() as conn:
        conn.autocommit(False)
        try:
            with conn.cursor() as cur:
                yield cur
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            raise
        finally:
            try:
                conn.autocommit(True)
            except Exception:  # noqa: BLE001
                pass


def query(sql: str, params: Sequence[Any] | None = None) -> List[Dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return list(cur.fetchall())


def query_one(sql: str, params: Sequence[Any] | None = None) -> Optional[Dict[str, Any]]:
    rows = query(sql, params)
    return rows[0] if rows else None


def query_scalar(sql: str, params: Sequence[Any] | None = None, default: Any = None) -> Any:
    row = query_one(sql, params)
    if not row:
        return default
    for value in row.values():
        return value
    return default


def execute(sql: str, params: Sequence[Any] | None = None) -> int:
    """执行写语句，返回受影响行数。INSERT 想拿自增 id 用 ``insert``。"""
    with connection() as conn:
        with conn.cursor() as cur:
            return cur.execute(sql, params or ())


def executemany(sql: str, seq: Iterable[Sequence[Any]]) -> int:
    rows = list(seq)
    if not rows:
        return 0
    with connection() as conn:
        with conn.cursor() as cur:
            return cur.executemany(sql, rows)


def insert(sql: str, params: Sequence[Any] | None = None) -> int:
    """执行 INSERT 并返回自增主键。"""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return int(cur.lastrowid or 0)


def ping() -> Dict[str, Any]:
    """健康检查：连得上就回服务端版本和当前库名。"""
    row = query_one("SELECT VERSION() AS version, DATABASE() AS db")
    if not row:
        return {"ok": False}
    return {"ok": True, "version": row.get("version"), "database": row.get("db")}


def ensure_database() -> None:
    """确保目标库存在。

    连接串里带了 database，库不存在时连接本身就会失败，所以这里先用一条**不指定库**的
    连接去 CREATE DATABASE IF NOT EXISTS。账号没有建库权限时不报致命错——很多人是先
    手工建好空库再给一个只有该库权限的账号，这种情况下建库失败是正常的，让后面的
    建表流程自己去撞真正的错误。
    """
    cfg = conf.mysql_config()
    try:
        conn = pymysql.connect(
            host=cfg["host"], port=cfg["port"], user=cfg["user"],
            password=cfg["password"], charset=cfg["charset"],
            cursorclass=DictCursor, autocommit=True, connect_timeout=10,
        )
    except Exception as exc:  # noqa: BLE001
        raise DatabaseError(
            f"无法连接 MySQL（{cfg['host']}:{cfg['port']}，用户 {cfg['user']}）：{exc}\n"
            f"请检查 conf.ini 中的 [mysql] 配置。"
        ) from exc
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET {cs} COLLATE {cs}_unicode_ci".format(
                    db=cfg["database"].replace("`", ""), cs=cfg["charset"]
                )
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("建库失败（可能是权限不足，若库已存在可忽略）：%s", exc)
    finally:
        _silent_close(conn)
