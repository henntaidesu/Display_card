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
    "returned",       # 已回国
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

# 整机设备里的部件类型。顺序即录入表单里「快捷添加」按钮的顺序。
# 内存 / 硬盘一台机器里往往有好几条，所以部件是**一台设备下的多行**，而不是设备上的字段。
DEVICE_PART_TYPES: List[str] = [
    "cpu",          # CPU
    "gpu",          # 显卡
    "ram",          # 内存
    "disk",         # 硬盘
    "motherboard",  # 主板
    "psu",          # 电源
    "cooler",       # 散热
    "case",         # 机箱
    "other",        # 其他
]

SOURCE_PLATFORMS: List[str] = ["yahoo", "mercari", "other"]

CURRENCIES: List[str] = ["JPY", "CNY"]

# 资金池只装日元：它模拟的是「先把人民币换成日元放在日本的账户里，再用这笔日元买卡」，
# 人民币不需要进池（rate 恒等于 1，进了池只会让 FIFO 里多一堆无意义的批次）。
POOL_CURRENCY: str = "JPY"

# 一张卡的采购资金从哪来。own = 自有资金（按交易日牌价折算，老逻辑）；
# pool = 从资金池扣，成本按被消耗的那几笔注资各自的汇率分段折算。
FUND_SOURCES: List[str] = ["own", "pool"]

# 资金池扣款的用途。purchase / intl_shipping 两类由卡片自动同步（跟着卡上的金额走），
# other 是手工记的池内杂项支出（手续费、代购费…），不计入任何一张卡的成本。
FUND_DRAW_CATEGORIES: List[str] = ["purchase", "intl_shipping", "other"]


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
            name         VARCHAR(128) NOT NULL,
            default_vram VARCHAR(32) NULL,
            sort_order   INT NOT NULL DEFAULT 0,
            created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_gpu_models_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='型号字典，独立于品牌。型号即芯片名，如 RTX 4090 / RTX 5090。'
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

            -- 采购资金从哪来。'own' 走 purchase_fx_rate（老逻辑）；'pool' 则由
            -- fund_draws / fund_allocations 按注资批次的汇率分段算出成本。
            fund_source VARCHAR(8) NOT NULL DEFAULT 'own',
            -- 下面三列是资金池分摊的**结果快照**，由 funds.rebuild() 统一回写。
            -- 冗余在卡片行上是为了让列表/统计不必为每一行再查一次分摊明细（N+1）。
            pool_purchase_cny DECIMAL(14,2) NULL COMMENT '购入价按各注资批次汇率折算后的人民币合计',
            pool_intl_cny     DECIMAL(14,2) NULL COMMENT '国际运费按各注资批次汇率折算后的人民币合计',
            pool_fx_rate      DECIMAL(18,8) NULL COMMENT '这张卡实际吃到的加权汇率，仅供展示',

            status     VARCHAR(24) NOT NULL DEFAULT 'purchased',
            note       TEXT NULL,
            -- 草稿卡：新增弹窗一打开就先建一张（好让图片能立刻挂上去），保存即转 0。
            -- 列表、统计一律只算 is_draft=0；未保存就关掉的草稿会被清理掉。
            is_draft   TINYINT(1) NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                           ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_cards_mgmt_no (mgmt_no),
            KEY idx_cards_status (status),
            KEY idx_cards_is_draft (is_draft),
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
        "devices",
        """
        CREATE TABLE IF NOT EXISTS devices (
            id       INT UNSIGNED NOT NULL AUTO_INCREMENT,
            mgmt_no  VARCHAR(32) NOT NULL COMMENT '系统管理编号 DEV-2026-0001',
            title    VARCHAR(128) NULL COMMENT '整机名称，如「戴尔 T7920 工作站」',

            source_platform VARCHAR(16) NULL COMMENT 'yahoo / mercari / other',
            seller          VARCHAR(128) NULL,
            item_url        VARCHAR(1024) NULL,
            order_no        VARCHAR(128) NULL,

            -- 采购只有**一笔总价**：整机是一口价买进来的，拆开来卖才产生多笔收入。
            -- 所以购入金额挂在设备上，出售金额挂在 device_parts 的每一行上。
            purchase_date          DATE NULL,
            purchase_amount        DECIMAL(14,2) NULL COMMENT '整机购入总价',
            purchase_currency      VARCHAR(3) NOT NULL DEFAULT 'JPY',
            intl_shipping_amount   DECIMAL(14,2) NULL,
            intl_shipping_currency VARCHAR(3) NOT NULL DEFAULT 'JPY',

            -- 汇率快照，口径与 cards 完全一致：取到就写死，之后不重算。
            purchase_fx_rate DECIMAL(18,8) NULL COMMENT '1 CNY = ? JPY，按 purchase_date',
            purchase_fx_date DATE NULL COMMENT '实际取到的牌价日（非交易日会回退）',

            -- 采购资金从哪来，与 cards 同一套语义：'own' 走 purchase_fx_rate；
            -- 'pool' 则由 fund_draws / fund_allocations 按注资批次的汇率分段算出成本。
            fund_source VARCHAR(8) NOT NULL DEFAULT 'own',
            pool_purchase_cny DECIMAL(14,2) NULL COMMENT '购入总价按各注资批次汇率折算后的人民币合计',
            pool_intl_cny     DECIMAL(14,2) NULL COMMENT '国际运费按各注资批次汇率折算后的人民币合计',
            pool_fx_rate      DECIMAL(18,8) NULL COMMENT '这台设备实际吃到的加权汇率，仅供展示',

            status     VARCHAR(24) NOT NULL DEFAULT 'purchased',
            note       TEXT NULL,
            -- 与卡片同一套草稿机制：新增弹窗一打开就先建一台，保存即转 0。
            is_draft   TINYINT(1) NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                           ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_devices_mgmt_no (mgmt_no),
            KEY idx_devices_status (status),
            KEY idx_devices_is_draft (is_draft),
            KEY idx_devices_purchase_date (purchase_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='整机设备：一次购入（一笔总价），拆成多个部件分别出售'
        """,
    ),
    (
        "device_parts",
        """
        CREATE TABLE IF NOT EXISTS device_parts (
            id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
            device_id INT UNSIGNED NOT NULL,
            -- cpu / gpu / ram / disk / motherboard / psu / cooler / case / other。
            -- 一台机器里内存、硬盘常常有好几条，所以它们是这张表里的**多行**，
            -- 而不是设备表上的多个字段——字段数写死了就装不下第三条内存。
            part_type VARCHAR(24) NOT NULL DEFAULT 'other',
            brand     VARCHAR(64) NULL,
            model     VARCHAR(128) NULL COMMENT '型号，如 i9-13900K / RTX 4090',
            spec      VARCHAR(128) NULL COMMENT '规格，如 32GB DDR5-6000 / 2TB NVMe',
            serial_no VARCHAR(128) NULL,
            quantity  INT NOT NULL DEFAULT 1 COMMENT '同规格几件合成一行（如 2 条 16G）',

            -- 出售侧：每个部件各卖各的价，一台设备因此有多个出售价格。
            sale_date                  DATE NULL,
            sale_amount                DECIMAL(14,2) NULL COMMENT '这一行的出售总价（含 quantity 件）',
            sale_currency              VARCHAR(3) NOT NULL DEFAULT 'CNY',
            domestic_shipping_amount   DECIMAL(14,2) NULL,
            domestic_shipping_currency VARCHAR(3) NOT NULL DEFAULT 'CNY',
            sale_fx_rate DECIMAL(18,8) NULL COMMENT '按本行 sale_date 取的牌价快照',
            sale_fx_date DATE NULL,

            buyer      VARCHAR(128) NULL,
            status     VARCHAR(24) NOT NULL DEFAULT 'purchased',
            note       VARCHAR(500) NULL,
            sort_order INT NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                           ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_device_parts_device (device_id, sort_order, id),
            KEY idx_device_parts_type (part_type),
            KEY idx_device_parts_sale_date (sale_date),
            CONSTRAINT fk_device_parts_device FOREIGN KEY (device_id)
                REFERENCES devices (id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='设备部件明细。一台设备多行，内存/硬盘可重复出现；出售价格在这里'
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
    (
        "fund_injections",
        """
        CREATE TABLE IF NOT EXISTS fund_injections (
            id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
            inject_date DATE NOT NULL COMMENT '这笔钱进池的日期，也是 FIFO 的排序依据',
            amount      DECIMAL(16,2) NOT NULL COMMENT '注入的日元金额',
            currency    VARCHAR(3) NOT NULL DEFAULT 'JPY',
            -- 换汇当时的汇率快照：1 人民币 = fx_rate 日元。这笔钱之后被谁用掉，
            -- 都按这个汇率折人民币成本 —— 池子里的钱是「已经用这个价换进来的」，
            -- 用它的那天市场价是多少与真实成本无关。
            fx_rate     DECIMAL(18,8) NULL,
            fx_date     DATE NULL COMMENT '实际取到的牌价日（非交易日会回退）',
            fx_manual   TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1=汇率手工填写（真实换汇价），不自动覆盖',
            channel     VARCHAR(64) NULL COMMENT '换汇渠道，如 银行电汇 / Wise，仅备注用',
            note        VARCHAR(500) NULL,
            created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_fund_injections_date (inject_date, id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='资金池注资批次。每次换汇进池一条，各自带自己那天的汇率'
        """,
    ),
    (
        "fund_draws",
        """
        CREATE TABLE IF NOT EXISTS fund_draws (
            id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
            -- 一笔扣款要么挂在一张卡上，要么挂在一台整机上，要么谁也不挂（手工记的
            -- 池内杂项支出）。两列互斥，永远最多只有一个非 NULL。
            card_id    INT UNSIGNED NULL COMMENT '归属卡片',
            device_id  INT UNSIGNED NULL COMMENT '归属整机设备',
            category   VARCHAR(24) NOT NULL DEFAULT 'purchase'
                           COMMENT 'purchase / intl_shipping 由卡片/整机自动同步；other 为手工记账',
            draw_date  DATE NOT NULL COMMENT '花钱的日期，决定它能吃到哪些批次（只能用已经进池的钱）',
            amount     DECIMAL(16,2) NOT NULL COMMENT '扣掉的日元金额',
            currency   VARCHAR(3) NOT NULL DEFAULT 'JPY',
            note       VARCHAR(500) NULL,
            -- 下面三列是 FIFO 分摊的结果，由 funds.rebuild() 回写：
            cny_amount DECIMAL(14,2) NULL COMMENT '折算后的人民币成本合计；NULL=有分段折不出来',
            shortfall  DECIMAL(16,2) NOT NULL DEFAULT 0 COMMENT '池子不够、没吃到注资的日元部分',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                           ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_fund_draws_date (draw_date, id),
            -- 一卡一类一条 / 一机一类一条。MySQL 的唯一键不约束含 NULL 的行，所以
            -- 手工支出（两列都为 NULL）以及另一种归属的行都不会被这两个键挡住。
            UNIQUE KEY uk_fund_draws_card_cat (card_id, category),
            UNIQUE KEY uk_fund_draws_device_cat (device_id, category),
            CONSTRAINT fk_fund_draws_card FOREIGN KEY (card_id)
                REFERENCES cards (id) ON DELETE CASCADE,
            CONSTRAINT fk_fund_draws_device FOREIGN KEY (device_id)
                REFERENCES devices (id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='从资金池扣款。卡片/整机侧的两类跟着各自的金额自动同步，删除时级联清掉'
        """,
    ),
    (
        "fund_allocations",
        """
        CREATE TABLE IF NOT EXISTS fund_allocations (
            id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
            draw_id      INT UNSIGNED NOT NULL,
            injection_id INT UNSIGNED NOT NULL,
            seq          INT NOT NULL DEFAULT 0 COMMENT '同一笔扣款内的分段顺序',
            amount       DECIMAL(16,2) NOT NULL COMMENT '这一段从该批次吃掉的日元',
            fx_rate      DECIMAL(18,8) NULL COMMENT '该批次的汇率快照（冗余，便于直接展示）',
            cny_amount   DECIMAL(14,2) NULL COMMENT 'amount / fx_rate；批次缺汇率时为 NULL',
            PRIMARY KEY (id),
            KEY idx_fund_alloc_draw (draw_id, seq),
            KEY idx_fund_alloc_injection (injection_id),
            CONSTRAINT fk_fund_alloc_draw FOREIGN KEY (draw_id)
                REFERENCES fund_draws (id) ON DELETE CASCADE,
            CONSTRAINT fk_fund_alloc_injection FOREIGN KEY (injection_id)
                REFERENCES fund_injections (id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='一笔扣款按 FIFO 拆到各注资批次上的明细。全量派生数据，
                   任何注资/扣款变动后由 funds.rebuild() 整体重算'
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
    ("cards", "is_draft", "is_draft TINYINT(1) NOT NULL DEFAULT 0"),
    ("cards", "fund_source", "fund_source VARCHAR(8) NOT NULL DEFAULT 'own'"),
    ("cards", "pool_purchase_cny", "pool_purchase_cny DECIMAL(14,2) NULL"),
    ("cards", "pool_intl_cny", "pool_intl_cny DECIMAL(14,2) NULL"),
    ("cards", "pool_fx_rate", "pool_fx_rate DECIMAL(18,8) NULL"),
    ("devices", "fund_source", "fund_source VARCHAR(8) NOT NULL DEFAULT 'own'"),
    ("devices", "pool_purchase_cny", "pool_purchase_cny DECIMAL(14,2) NULL"),
    ("devices", "pool_intl_cny", "pool_intl_cny DECIMAL(14,2) NULL"),
    ("devices", "pool_fx_rate", "pool_fx_rate DECIMAL(18,8) NULL"),
    ("fund_draws", "device_id", "device_id INT UNSIGNED NULL"),
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


def _has_column(table: str, column: str) -> bool:
    return int(db.query_scalar(
        "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (table, column), default=0) or 0) > 0


def _has_index(table: str, index: str) -> bool:
    return int(db.query_scalar(
        "SELECT COUNT(*) AS c FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s",
        (table, index), default=0) or 0) > 0


def _migrate_gpu_models_standalone() -> None:
    """把 gpu_models 从「依附品牌」迁成独立型号表：去掉 brand_id 及其相关索引，
    唯一键改到 name 上。CREATE TABLE IF NOT EXISTS 动不了已存在的旧表，只能在这里 ALTER。"""
    if not _has_column("gpu_models", "brand_id"):
        return  # 已是新结构，无需迁移
    log.info("迁移：gpu_models 解除与品牌的关联，改为独立型号表")
    # 先删掉引用 brand_id 的旧索引，之后才能删列
    if _has_index("gpu_models", "uk_gpu_models_brand_name"):
        db.execute("ALTER TABLE gpu_models DROP INDEX uk_gpu_models_brand_name")
    if _has_index("gpu_models", "idx_gpu_models_brand"):
        db.execute("ALTER TABLE gpu_models DROP INDEX idx_gpu_models_brand")
    # 旧结构允许跨品牌同名，去 brand 后同名会撞新唯一键：同名只保留 id 最小的一条
    db.execute("DELETE m1 FROM gpu_models m1 JOIN gpu_models m2 ON m1.name = m2.name AND m1.id > m2.id")
    db.execute("ALTER TABLE gpu_models DROP COLUMN brand_id")
    if not _has_index("gpu_models", "uk_gpu_models_name"):
        db.execute("ALTER TABLE gpu_models ADD UNIQUE KEY uk_gpu_models_name (name)")


def _migrate_fund_draws_devices() -> None:
    """给已存在的 fund_draws 补上整机归属所需的唯一键与外键。

    device_id 这一列由 _MIGRATIONS 补上，但唯一键和外键 ALTER 不了已建好的表
    （CREATE TABLE IF NOT EXISTS 对老表是空操作），只能在这里按需加。
    """
    if not _has_column("fund_draws", "device_id"):
        return  # 列还没补上（建表刚失败？），索引无从谈起
    if not _has_index("fund_draws", "uk_fund_draws_device_cat"):
        log.info("迁移：fund_draws 增加整机侧唯一键")
        db.execute("ALTER TABLE fund_draws ADD UNIQUE KEY uk_fund_draws_device_cat (device_id, category)")
    has_fk = int(db.query_scalar(
        "SELECT COUNT(*) AS c FROM information_schema.TABLE_CONSTRAINTS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'fund_draws' "
        "AND CONSTRAINT_NAME = 'fk_fund_draws_device'", default=0) or 0)
    if not has_fk:
        log.info("迁移：fund_draws 增加指向 devices 的外键")
        db.execute(
            "ALTER TABLE fund_draws ADD CONSTRAINT fk_fund_draws_device "
            "FOREIGN KEY (device_id) REFERENCES devices (id) ON DELETE CASCADE"
        )


def init() -> None:
    """建库 → 建表 → 补列 → 结构迁移 → 灌入首次运行的种子数据。可重复执行。"""
    db.ensure_database()
    for name, ddl in _TABLES:
        db.execute(ddl)
        log.debug("表就绪：%s", name)
    for table, column, ddl in _MIGRATIONS:
        _ensure_column(table, column, ddl)
    _migrate_gpu_models_standalone()
    _migrate_fund_draws_devices()
    _cleanup_stale_drafts()
    _seed()


def _cleanup_stale_drafts() -> None:
    """清掉超过 2 小时没定稿的草稿（卡片与整机都算）。

    正常流程里草稿要么保存（转正）、要么关弹窗时被删；只有「开了新增弹窗又直接关掉浏览器」
    才会残留。2 小时的阈值保证正在编辑中的草稿（刚建几秒）不会被误删，即使期间热重载了。
    连带 card_media / device_parts 由外键级联删除；图床上的文件成孤儿（可接受，仅占空间）。
    """
    try:
        removed_devices = db.execute(
            "DELETE FROM devices WHERE is_draft = 1 AND created_at < (NOW() - INTERVAL 2 HOUR)"
        )
        if removed_devices:
            log.info("清理了 %d 台过期草稿设备", removed_devices)
        removed_cards = db.execute(
            "DELETE FROM cards WHERE is_draft = 1 AND created_at < (NOW() - INTERVAL 2 HOUR)"
        )
        if removed_cards:
            log.info("清理了 %d 张过期草稿卡", removed_cards)
        if removed_cards or removed_devices:
            # 草稿上若开过「从资金池扣除」，它的扣款刚被外键连带删掉了：重算一次，
            # 把那笔钱还给池子，后面的扣款也才吃得到。在函数里 import 是为了避开
            # funds → schema 的循环依赖。
            from src import funds

            funds.rebuild()
    except Exception as exc:  # noqa: BLE001  清理失败不该拖垮启动
        log.warning("清理草稿失败：%s", exc)


def _seed() -> None:
    """首次运行的种子数据：只建默认管理员。品牌与型号一律由用户手动添加，不预置。"""
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
