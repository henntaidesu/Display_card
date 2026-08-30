# -*- coding: utf-8 -*-
"""建表与轻量迁移。

启动时无条件跑一遍：``CREATE TABLE IF NOT EXISTS`` 保证新库能自建，``_ensure_column``
保证老库能补上后加的字段。没有版本号表——这个系统的演进方式是「只加不改」，
把每次新增的列写进 _MIGRATIONS 即可，跑多少次都一样。
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from src import db

log = logging.getLogger(__name__)


# ── 枚举取值（后端唯一事实来源，前端通过 /options 端点拿）────────────────── #

# 状态是**一条单线**：已购入 → 待测试 → 测试通过 / 测试不通过 → 回国中 → 转寄中
# → 已签收 → 已打款。「已签收」「已打款」是中国买家的动作，走到「已打款」这笔生意才算完。
# 「测试不通过」是分叉终点，通常不会再往后走（卡有问题，退货或另行处理）。
CARD_STATUSES: List[str] = [
    "purchased",      # 已购入
    "pending_test",   # 待测试
    "test_passed",    # 测试通过
    "test_failed",    # 测试不通过
    "returning",      # 回国中
    "forwarding",     # 转寄中
    "received",       # 已签收（买家）
    "paid",           # 已打款（买家）
]

# 图片/视频分类。顺序即前端标签页顺序。
MEDIA_CATEGORIES: List[str] = [
    "appearance",  # 显卡外观
    "pcb",         # PCB 外观
    "gpu_core",    # GPU 核心
    "gpuz",        # GPU-Z
    "mods",        # mods 测试
]

SOURCE_PLATFORMS: List[str] = ["yahoo", "mercari", "other"]

CURRENCIES: List[str] = ["JPY", "CNY"]


# ── 表定义 ──────────────────────────────────────────────────────────────── #

_TABLES: List[Tuple[str, str]] = [
    (
        "app_settings",
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            `key`        VARCHAR(128) NOT NULL,
            `value`      TEXT NULL,
            updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                             ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`key`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='除 MySQL 连接以外的全部配置：图床连接、汇率来源、系统参数'
        """,
    ),
    (
        "users",
        """
        CREATE TABLE IF NOT EXISTS users (
            id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
            username       VARCHAR(64) NOT NULL,
            password_hash  VARCHAR(255) NOT NULL,
            is_active      TINYINT(1) NOT NULL DEFAULT 1,
            is_admin       TINYINT(1) NOT NULL DEFAULT 0,
            token_version  INT UNSIGNED NOT NULL DEFAULT 0,
            last_active_at DATETIME NULL,
            created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_users_username (username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
    ),
    (
        "gpu_brands",
        """
        CREATE TABLE IF NOT EXISTS gpu_brands (
            id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
            name       VARCHAR(64) NOT NULL,
            sort_order INT NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_gpu_brands_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='品牌字典（华硕/微星/技嘉…），录卡时下拉选，可现场新增'
        """,
    ),
    (
        "gpu_models",
        """
        CREATE TABLE IF NOT EXISTS gpu_models (
            id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
            brand_id     INT UNSIGNED NULL,
            name         VARCHAR(128) NOT NULL,
            default_vram VARCHAR(32) NULL,
            sort_order   INT NOT NULL DEFAULT 0,
            created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_gpu_models_brand_name (brand_id, name),
            KEY idx_gpu_models_brand (brand_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='型号字典。default_vram 让选完型号自动带出显存，少敲一次'
        """,
    ),
    (
        "cards",
        """
        CREATE TABLE IF NOT EXISTS cards (
            id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
            mgmt_no       VARCHAR(32) NOT NULL COMMENT '系统管理编号 GPU-2026-0001',
            brand         VARCHAR(64) NULL,
            model         VARCHAR(128) NULL,
            vram          VARCHAR(32) NULL,
            serial_no     VARCHAR(128) NULL COMMENT '显卡实体序列号',

            source_platform VARCHAR(16) NULL COMMENT 'yahoo / mercari / other',
            seller          VARCHAR(128) NULL,
            item_url        VARCHAR(1024) NULL,
            order_no        VARCHAR(128) NULL,

            purchase_date            DATE NULL,
            purchase_amount          DECIMAL(14,2) NULL,
            purchase_currency        VARCHAR(3) NOT NULL DEFAULT 'JPY',
            intl_shipping_amount     DECIMAL(14,2) NULL,
            intl_shipping_currency   VARCHAR(3) NOT NULL DEFAULT 'JPY',
            domestic_shipping_amount DECIMAL(14,2) NULL,
            domestic_shipping_currency VARCHAR(3) NOT NULL DEFAULT 'CNY',
            sale_date                DATE NULL,
            sale_amount              DECIMAL(14,2) NULL,
            sale_currency            VARCHAR(3) NOT NULL DEFAULT 'CNY',

            -- 汇率快照。取到就写死在行里，之后再也不重算：
            -- 汇率每天在动，不快照的话昨天算出来的利润今天会自己变。
            purchase_fx_rate DECIMAL(18,8) NULL COMMENT '1 JPY = ? CNY，按 purchase_date',
            purchase_fx_date DATE NULL COMMENT '实际取到的牌价日（周末/节假日会回退到前一工作日）',
            sale_fx_rate     DECIMAL(18,8) NULL COMMENT '1 JPY = ? CNY，按 sale_date',
            sale_fx_date     DATE NULL,
            fx_manual        TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1=汇率被手工改过，自动刷新时跳过',

            status     VARCHAR(24) NOT NULL DEFAULT 'purchased',
            note       TEXT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                           ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_cards_mgmt_no (mgmt_no),
            KEY idx_cards_status (status),
            KEY idx_cards_purchase_date (purchase_date),
            KEY idx_cards_sale_date (sale_date),
            KEY idx_cards_serial (serial_no)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
    ),
    (
        "card_media",
        """
        CREATE TABLE IF NOT EXISTS card_media (
            id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
            card_id     INT UNSIGNED NOT NULL,
            category    VARCHAR(24) NOT NULL COMMENT 'appearance/pcb/gpu_core/gpuz/mods',
            kind        VARCHAR(8) NOT NULL DEFAULT 'image' COMMENT 'image / video',
            -- 图床侧的存储名，删除和查详情都靠它
            stored_name VARCHAR(255) NOT NULL,
            public_url  VARCHAR(1024) NOT NULL,
            filename    VARCHAR(255) NULL COMMENT '上传时的原始文件名，仅供展示',
            mime_type   VARCHAR(128) NULL,
            size_bytes  BIGINT UNSIGNED NULL,
            sort_order  INT NOT NULL DEFAULT 0,
            created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_card_media_card (card_id, category, sort_order),
            CONSTRAINT fk_card_media_card FOREIGN KEY (card_id)
                REFERENCES cards (id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='文件本体在图床，这里只存指针'
        """,
    ),
    (
        "card_status_logs",
        """
        CREATE TABLE IF NOT EXISTS card_status_logs (
            id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
            card_id     INT UNSIGNED NOT NULL,
            from_status VARCHAR(24) NULL,
            to_status   VARCHAR(24) NOT NULL,
            note        VARCHAR(500) NULL,
            occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_card_status_logs_card (card_id, occurred_at),
            CONSTRAINT fk_card_status_logs_card FOREIGN KEY (card_id)
                REFERENCES cards (id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='状态流转history，用于「这张卡在海关卡了多久」这类追溯'
        """,
    ),
    (
        "fx_rates",
        """
        CREATE TABLE IF NOT EXISTS fx_rates (
            rate_date  DATE NOT NULL,
            base       VARCHAR(3) NOT NULL,
            quote      VARCHAR(3) NOT NULL,
            rate       DECIMAL(18,8) NOT NULL,
            source     VARCHAR(32) NOT NULL DEFAULT 'ecb',
            fetched_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (rate_date, base, quote, source)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='汇率本地缓存。历史牌价一经公布就不再变，缓存下来永久有效，
                   既省接口调用，也保证断网时历史数据照样算得出来'
        """,
    ),
]


# 后加的列写在这里：(表名, 列名, 完整的 ADD COLUMN 定义)
#
# CREATE TABLE IF NOT EXISTS 对已存在的表是空操作，所以当目标库里事先就有一张
# 同名旧表（比如上一版本建的、或别处留下的 users）时，新加的列不会自动补上，运行时会撞
# "Unknown column"。凡是后来才加进表定义的列，都必须在这里登记一条，让 _ensure_column
# 在启动时按需补齐。已存在的列会被跳过，重复执行安全。
_MIGRATIONS: List[Tuple[str, str, str]] = [
    ("users", "is_active", "is_active TINYINT(1) NOT NULL DEFAULT 1"),
    ("users", "is_admin", "is_admin TINYINT(1) NOT NULL DEFAULT 0"),
    ("users", "token_version", "token_version INT UNSIGNED NOT NULL DEFAULT 0"),
    ("users", "last_active_at", "last_active_at DATETIME NULL"),
]


def _ensure_column(table: str, column: str, ddl: str) -> None:
    exists = db.query_scalar(
        "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (table, column),
        default=0,
    )
    if int(exists or 0) > 0:
        return
    log.info("迁移：为 %s 添加列 %s", table, column)
    db.execute("ALTER TABLE `{t}` ADD COLUMN {ddl}".format(t=table.replace("`", ""), ddl=ddl))


def init() -> None:
    """建库 → 建表 → 补列 → 灌入首次运行的种子数据。可重复执行。"""
    db.ensure_database()
    for name, ddl in _TABLES:
        db.execute(ddl)
        log.debug("表就绪：%s", name)
    for table, column, ddl in _MIGRATIONS:
        _ensure_column(table, column, ddl)
    _seed()


def _seed() -> None:
    """首次运行的种子数据：默认管理员 + 常见品牌。已有数据时什么都不做。"""
    from src.security import hash_password

    # 按用户名判断而不是 COUNT==0：库里若已有一张旧的 users 表（有其他行、但没有 admin），
    # 用 COUNT 判断会以为「已初始化」而跳过，导致没有可登录的账号。
    admin = db.query_one("SELECT id, is_admin FROM users WHERE username = %s", ("admin",))
    if not admin:
        db.insert(
            "INSERT INTO users (username, password_hash, is_active, is_admin) VALUES (%s, %s, 1, 1)",
            ("admin", hash_password("admin")),
        )
        log.warning("已创建默认管理员 admin / admin —— 请登录后立即在「系统配置」中改密码")
    elif not admin["is_admin"]:
        # 旧表迁移后 is_admin 默认补成了 0：把内置的 admin 账号提回管理员，
        # 否则它进不了「系统配置」里的数据库/账号等管理员专属页面。
        db.execute("UPDATE users SET is_admin = 1 WHERE id = %s", (admin["id"],))
        log.info("已将已存在的 admin 账号提升为管理员")

    brand_count = int(db.query_scalar("SELECT COUNT(*) AS c FROM gpu_brands", default=0) or 0)
    if brand_count == 0:
        brands = [
            "ASUS", "MSI", "GIGABYTE", "ZOTAC", "COLORFUL", "GALAX",
            "PALIT", "INNO3D", "EVGA", "SAPPHIRE", "PowerColor", "XFX",
            "NVIDIA", "AMD", "ELSA", "玄人志向",
        ]
        db.executemany(
            "INSERT INTO gpu_brands (name, sort_order) VALUES (%s, %s)",
            [(name, index) for index, name in enumerate(brands)],
        )
        log.info("已灌入 %d 个默认品牌", len(brands))
