# -*- coding: utf-8 -*-
"""资金池：注资批次、扣款、FIFO 分摊与人民币成本换算。

**为什么需要它**：先换一笔日元放在日本的账户里，再陆续用这笔钱买卡——这时一张卡的
真实人民币成本，取决于「买它的钱是哪一批换进来的、当时换汇价多少」，而不是买卡那天
的市场牌价。同一天买的两张卡，如果吃的是不同批次的钱，成本就不一样。

**模型**（三张表）：

- ``fund_injections`` 注资批次：一次换汇进池一条，带自己那天的汇率快照。
- ``fund_draws`` 扣款：卡片与整机侧的「购入价 / 国际运费」跟着各自的金额自动同步
  （一卡一类一条 / 一机一类一条），另有手工记的池内杂项支出。
- ``fund_allocations`` 分摊明细：一笔扣款按 FIFO 拆到若干批次上，每段带该批次的汇率。

**FIFO 与两条硬规则**：

1. 先进先出，按 ``inject_date`` 排序——最早换进来的钱先花掉。
2. 一笔扣款只能吃 ``inject_date <= draw_date`` 的批次：还没进池的钱花不出去。
   吃不满的部分记为 ``shortfall``（当时池内余额不够），按当日市场牌价折算并给出
   警告，而不是硬凑到后面的批次上——那会让成本凭空变好看。

**分摊是全量派生数据**：任何注资或扣款变动后都整体重算（``rebuild()``），而不是增量
维护。理由是「补录一笔上个月的注资」会改变它之后所有扣款的分摊结果，增量算法要处理
的回溯情形远比全量重算复杂，而这个系统的数据量（几百条）重算一次不到几十毫秒。

算完把分摊结果回写到 ``cards`` / ``devices`` 的 ``pool_purchase_cny / pool_intl_cny /
pool_fx_rate``，列表页和统计就不用为每一行再查一次明细（N+1）。两张表的这三列同名同义，
所以下面的同步与回写都写成「按归属方」的一套代码，而不是复制两份。
"""

from __future__ import annotations

import datetime as dt
import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from src import db
from src.fx import FxError, get_rate
from src.schema import POOL_CURRENCY

log = logging.getLogger(__name__)

_CENT = Decimal("0.01")
_ZERO = Decimal("0")

# 由系统自动同步的两类扣款 → 回写到归属行上的哪一列
_CARD_CATEGORIES = {
    "purchase": "pool_purchase_cny",
    "intl_shipping": "pool_intl_cny",
}

# 扣款的两种归属：卡片和整机。值是 (外键列, 目标表)。两张表的分摊快照列同名，
# 所以同步与回写共用一套代码，只有这两个名字不同。
_OWNERS = {
    "card": ("card_id", "cards"),
    "device": ("device_id", "devices"),
}


# ── 小工具 ──────────────────────────────────────────────────────────────── #

def _dec(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _round(value: Optional[Decimal]) -> Optional[Decimal]:
    if value is None:
        return None
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _float(value: Any) -> Optional[float]:
    value = _dec(value)
    return float(value) if value is not None else None


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return str(value)


def _to_cny(amount: Optional[Decimal], rate: Optional[Decimal]) -> Optional[Decimal]:
    """日元 → 人民币。rate 是「1 人民币 = rate 日元」，所以是除法（与 cards._to_cny 同口径）。"""
    if amount is None or rate is None or rate <= 0:
        return None
    return _round(amount / rate)


# ── 注资的汇率 ──────────────────────────────────────────────────────────── #

def resolve_injection_fx(
    inject_date: dt.date,
    manual_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """定这批钱的汇率：手填优先（那才是真实换汇价），否则按注资日取牌价。

    取不到不抛异常——先把注资记下来，汇率留空之后再补；只是在它被补上之前，吃到这批
    钱的卡片成本会显示成「缺汇率」，而不是一个猜出来的数字。
    """
    out: Dict[str, Any] = {"fx_rate": None, "fx_date": None, "fx_manual": 0, "warnings": []}
    if manual_rate:
        out.update({"fx_rate": manual_rate, "fx_date": inject_date, "fx_manual": 1})
        return out
    try:
        result = get_rate(inject_date)
    except FxError as exc:
        out["warnings"].append(f"注资日汇率获取失败：{exc}")
        return out
    out["fx_rate"] = result["rate"]
    out["fx_date"] = result["rate_date"]
    if result["stale"]:
        out["warnings"].append(f"{inject_date} 无牌价，已回退到 {result['rate_date']} 的汇率")
    elif result["rate_date"] != inject_date:
        out["warnings"].append(f"{inject_date} 是非交易日，采用 {result['rate_date']} 的牌价")
    return out


# ── FIFO 分摊（纯函数，不碰数据库，便于单独验算）──────────────────────────── #

def allocate(
    injections: List[Dict[str, Any]],
    draws: List[Dict[str, Any]],
    market_rate: Any = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """把每笔扣款按 FIFO 拆到注资批次上。

    ``injections`` 必须按 (inject_date, id) 升序，``draws`` 按 (draw_date, id) 升序——
    扣款也要按时间顺序处理，否则「谁先花掉了那批便宜的钱」会取决于录入顺序。

    ``market_rate`` 是个 ``(date) -> Decimal | None`` 的函数，用于折算池子不够的部分。

    返回 ``(分摊行, 每笔扣款的汇总)``。
    """
    remaining: Dict[int, Decimal] = {
        int(inj["id"]): (_dec(inj["amount"]) or _ZERO) for inj in injections
    }
    allocations: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []

    for draw in draws:
        need = _dec(draw["amount"]) or _ZERO
        draw_date = draw["draw_date"]
        seq = 0
        lines: List[Dict[str, Any]] = []
        cny_total: Optional[Decimal] = _ZERO
        jpy_converted = _ZERO

        for inj in injections:
            if need <= 0:
                break
            # 注资已按日期升序：碰到晚于扣款日的批次，后面的只会更晚，直接收工
            if draw_date and inj["inject_date"] and inj["inject_date"] > draw_date:
                break
            available = remaining.get(int(inj["id"]), _ZERO)
            if available <= 0:
                continue
            take = available if available < need else need
            rate = _dec(inj.get("fx_rate"))
            cny = _to_cny(take, rate)
            remaining[int(inj["id"])] = available - take
            need -= take
            lines.append({
                "draw_id": int(draw["id"]),
                "injection_id": int(inj["id"]),
                "seq": seq,
                "amount": take,
                "fx_rate": rate,
                "cny_amount": cny,
            })
            seq += 1
            # 任何一段折不出来（该批次还没汇率），整笔扣款的人民币成本就作废：
            # 拿「能算的那部分」当合计，会得到一个明显偏低却看不出问题的成本。
            if cny is None:
                cny_total = None
            elif cny_total is not None:
                cny_total += cny
                jpy_converted += take

        shortfall = need if need > 0 else _ZERO
        if shortfall > 0:
            fallback = market_rate(draw_date) if callable(market_rate) else _dec(market_rate)
            short_cny = _to_cny(shortfall, _dec(fallback))
            if short_cny is None:
                cny_total = None
            elif cny_total is not None:
                cny_total += short_cny
                jpy_converted += shortfall

        allocations.extend(lines)
        results.append({
            "draw": draw,
            "lines": lines,
            "cny_amount": _round(cny_total),
            "shortfall": shortfall,
            # 这笔钱实际吃到的加权汇率 = 花掉的日元 ÷ 折出来的人民币
            "effective_rate": (jpy_converted / cny_total)
            if (cny_total is not None and cny_total > 0 and jpy_converted > 0) else None,
        })

    return allocations, results


# ── 重算 ────────────────────────────────────────────────────────────────── #

def _market_rate_lookup():
    """按日期取市场牌价，只读本地缓存。

    重算会在每次存卡时触发，这里**不打网络**：几十笔扣款各打一次外部接口，会把一次
    保存拖成好几秒，而这个值只用于「池子不够」的兜底部分。取不到就留空（显示为不完整）。
    """
    memo: Dict[Any, Optional[Decimal]] = {}

    def lookup(date: Optional[dt.date]) -> Optional[Decimal]:
        if not date:
            return None
        if date not in memo:
            try:
                memo[date] = _dec(get_rate(date, allow_network=False)["rate"])
            except FxError:
                memo[date] = None
        return memo[date]

    return lookup


def rebuild() -> Dict[str, Any]:
    """整体重算全部分摊，并把结果回写到扣款行与它的归属行。可重复执行，结果幂等。"""
    injections = db.query(
        "SELECT id, inject_date, amount, fx_rate FROM fund_injections "
        "ORDER BY inject_date, id"
    )
    draws = db.query(
        "SELECT id, card_id, device_id, category, draw_date, amount FROM fund_draws "
        "ORDER BY draw_date, id"
    )
    allocations, results = allocate(injections, draws, _market_rate_lookup())

    # 每个归属方（一张卡 / 一台整机）把它的两类扣款汇总起来，一次性回写。
    # key 里带上归属类型：卡片和整机的 id 各自从 1 开始，只用 id 会把两者混在一起。
    owner_values: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for res in results:
        draw = res["draw"]
        if draw["category"] not in _CARD_CATEGORIES:
            continue
        owner = next(
            ((kind, int(draw[col])) for kind, (col, _t) in _OWNERS.items() if draw.get(col)),
            None,
        )
        if owner is None:
            continue  # 手工记的池内支出，不属于任何一行
        bucket = owner_values.setdefault(owner, {
            "pool_purchase_cny": None, "pool_intl_cny": None,
            "_jpy": _ZERO, "_cny": _ZERO, "_broken": False,
        })
        bucket[_CARD_CATEGORIES[draw["category"]]] = res["cny_amount"]
        if res["cny_amount"] is None:
            bucket["_broken"] = True
        else:
            bucket["_jpy"] += _dec(draw["amount"]) or _ZERO
            bucket["_cny"] += res["cny_amount"]

    with db.transaction() as cur:
        # 分摊行全删重插：它是纯派生数据，没有任何外部引用指向它
        cur.execute("DELETE FROM fund_allocations")
        if allocations:
            cur.executemany(
                "INSERT INTO fund_allocations (draw_id, injection_id, seq, amount, fx_rate, cny_amount) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [(a["draw_id"], a["injection_id"], a["seq"], a["amount"], a["fx_rate"], a["cny_amount"])
                 for a in allocations],
            )
        for res in results:
            cur.execute(
                "UPDATE fund_draws SET cny_amount = %s, shortfall = %s WHERE id = %s",
                (res["cny_amount"], res["shortfall"], res["draw"]["id"]),
            )
        # 先把两张表的分摊快照都清空，再写回有扣款的那些：漏清的话，一行改回「自有资金」
        # 之后仍留着上一次的池成本，成本就永远停在旧值上。
        for _col, table in _OWNERS.values():
            cur.execute(
                f"UPDATE {table} SET pool_purchase_cny = NULL, pool_intl_cny = NULL, "
                f"pool_fx_rate = NULL WHERE pool_purchase_cny IS NOT NULL "
                f"OR pool_intl_cny IS NOT NULL OR pool_fx_rate IS NOT NULL"
            )
        for (kind, owner_id), bucket in owner_values.items():
            rate = None
            if not bucket["_broken"] and bucket["_cny"] > 0 and bucket["_jpy"] > 0:
                rate = bucket["_jpy"] / bucket["_cny"]
            # 表名来自 _OWNERS 这张固定的表，不是外部输入，拼进 SQL 是安全的
            cur.execute(
                f"UPDATE {_OWNERS[kind][1]} SET pool_purchase_cny = %s, pool_intl_cny = %s, "
                f"pool_fx_rate = %s WHERE id = %s",
                (bucket["pool_purchase_cny"], bucket["pool_intl_cny"], rate, owner_id),
            )

    warnings: List[str] = []
    short = [r for r in results if r["shortfall"] > 0]
    if short:
        warnings.append(f"有 {len(short)} 笔扣款超出了当时的池内余额，超出部分按当日市场牌价折算")
    missing = [r for r in results if r["cny_amount"] is None]
    if missing:
        warnings.append(f"有 {len(missing)} 笔扣款因缺少汇率算不出人民币成本")
    return {
        "draws": len(results),
        "allocations": len(allocations),
        "owners": len(owner_values),
        "warnings": warnings,
    }


# ── 归属方（卡片 / 整机）扣款的同步 ─────────────────────────────────────── #

def sync_owner_draws(kind: str, owner_id: int, row: Optional[Dict[str, Any]] = None) -> bool:
    """让一张卡 / 一台整机的池内扣款与它上面的金额保持一致，返回是否发生了改动。

    卡片和整机在这件事上完全同构：都有 fund_source、purchase_amount、
    intl_shipping_amount 和对应的币种，区别只是扣款行挂在哪一列上。所以这里写成
    一套，靠 ``_OWNERS`` 里的 (外键列, 表名) 分流——复制两份的下场是改了一边忘了
    另一边，而这种账目上的不一致要等到对不上数才会被发现。

    「一卡一类一条 / 一机一类一条」由唯一键保证，所以这里按 category 做 upsert 而不是
    先删后插——先删后插会让 id 每次保存都变，分摊明细也就没法追溯了。
    只有日元金额进池：池子装的是日元，人民币支出与它无关（照旧走牌价折算）。
    """
    col, table = _OWNERS[kind]
    row = row or db.query_one(f"SELECT * FROM {table} WHERE id = %s", (owner_id,))
    if not row:
        return False
    use_pool = (row.get("fund_source") or "own") == "pool"
    draw_date = row.get("purchase_date") or dt.date.today()

    wanted: Dict[str, Decimal] = {}
    if use_pool:
        for category, amount_key, currency_key in (
            ("purchase", "purchase_amount", "purchase_currency"),
            ("intl_shipping", "intl_shipping_amount", "intl_shipping_currency"),
        ):
            amount = _dec(row.get(amount_key))
            currency = (row.get(currency_key) or "").upper()
            if amount and amount > 0 and currency == POOL_CURRENCY:
                wanted[category] = amount

    existing = {
        r["category"]: r for r in db.query(
            f"SELECT id, category, draw_date, amount FROM fund_draws WHERE {col} = %s",
            (owner_id,),
        )
    }
    changed = False

    for category in _CARD_CATEGORIES:
        want = wanted.get(category)
        have = existing.get(category)
        if want is None:
            if have:
                db.execute("DELETE FROM fund_draws WHERE id = %s", (have["id"],))
                changed = True
            continue
        if not have:
            db.insert(
                f"INSERT INTO fund_draws ({col}, category, draw_date, amount, currency) "
                f"VALUES (%s, %s, %s, %s, %s)",
                (owner_id, category, draw_date, want, POOL_CURRENCY),
            )
            changed = True
        elif _dec(have["amount"]) != want or have["draw_date"] != draw_date:
            db.execute(
                "UPDATE fund_draws SET draw_date = %s, amount = %s WHERE id = %s",
                (draw_date, want, have["id"]),
            )
            changed = True

    return changed


def sync_and_rebuild(kind: str, owner_id: int, row: Optional[Dict[str, Any]] = None) -> None:
    """存卡 / 存整机后调用：同步扣款，真的有变化时才重算。

    「有变化才重算」不只是省事——保存是防抖自动触发的（改一个字段就是一次 PUT），
    每次都全量重算会把大量无谓的写打到库上。
    """
    try:
        if sync_owner_draws(kind, owner_id, row):
            rebuild()
    except Exception as exc:  # noqa: BLE001  资金池算不动不该让保存失败
        log.warning("同步%s %s 的资金池扣款失败：%s", kind, owner_id, exc)


def sync_card_draws(card_id: int, row: Optional[Dict[str, Any]] = None) -> bool:
    return sync_owner_draws("card", card_id, row)


def sync_card_and_rebuild(card_id: int, row: Optional[Dict[str, Any]] = None) -> None:
    sync_and_rebuild("card", card_id, row)


def sync_device_and_rebuild(device_id: int, row: Optional[Dict[str, Any]] = None) -> None:
    sync_and_rebuild("device", device_id, row)


# ── 查询 ────────────────────────────────────────────────────────────────── #

def list_injections() -> List[Dict[str, Any]]:
    """注资列表，带每批的已用 / 剩余。已用量从分摊明细汇总，池子的账永远自洽。"""
    rows = db.query(
        "SELECT i.*, COALESCE(SUM(a.amount), 0) AS used_amount, "
        "       COALESCE(SUM(a.cny_amount), 0) AS used_cny "
        "FROM fund_injections i LEFT JOIN fund_allocations a ON a.injection_id = i.id "
        "GROUP BY i.id ORDER BY i.inject_date DESC, i.id DESC"
    )
    out = []
    for row in rows:
        amount = _dec(row["amount"]) or _ZERO
        used = _dec(row["used_amount"]) or _ZERO
        rate = _dec(row["fx_rate"])
        out.append({
            "id": row["id"],
            "inject_date": _iso(row["inject_date"]),
            "amount": _float(amount),
            "currency": row["currency"],
            "fx_rate": _float(rate),
            "fx_date": _iso(row["fx_date"]),
            "fx_manual": bool(row["fx_manual"]),
            "channel": row["channel"],
            "note": row["note"],
            "cny_cost": _float(_to_cny(amount, rate)),
            "used_amount": _float(used),
            "used_cny": _float(row["used_cny"]),
            "remaining_amount": _float(amount - used),
            "remaining_cny": _float(_to_cny(amount - used, rate)),
            "created_at": _iso(row["created_at"]),
        })
    return out


def _draw_allocations(draw_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
    if not draw_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(draw_ids))
    rows = db.query(
        f"SELECT a.*, i.inject_date FROM fund_allocations a "
        f"JOIN fund_injections i ON i.id = a.injection_id "
        f"WHERE a.draw_id IN ({placeholders}) ORDER BY a.draw_id, a.seq",
        draw_ids,
    )
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(int(row["draw_id"]), []).append({
            "injection_id": row["injection_id"],
            "inject_date": _iso(row["inject_date"]),
            "amount": _float(row["amount"]),
            "fx_rate": _float(row["fx_rate"]),
            "cny_amount": _float(row["cny_amount"]),
        })
    return grouped


def list_draws(
    card_id: Optional[int] = None,
    device_id: Optional[int] = None,
    limit: int = 300,
) -> List[Dict[str, Any]]:
    """扣款列表，每笔带它的分段明细（吃了哪几批钱、各按什么汇率折算）。

    每行都带上归属方：``owner_kind`` 是 card / device / None（手工记的池内支出），
    ``owner_name`` 与 ``mgmt_no`` 取自对应的那张表——前端只看这三个字段就能显示，
    不必自己判断该读 card 还是 device 的哪个字段。
    """
    where, params = "", []
    if card_id:
        where = " WHERE d.card_id = %s"
        params.append(card_id)
    elif device_id:
        where = " WHERE d.device_id = %s"
        params.append(device_id)
    rows = db.query(
        "SELECT d.*, c.mgmt_no AS card_mgmt_no, c.brand, c.model, "
        "       v.mgmt_no AS device_mgmt_no, v.title AS device_title "
        "FROM fund_draws d "
        "LEFT JOIN cards c ON c.id = d.card_id "
        "LEFT JOIN devices v ON v.id = d.device_id"
        f"{where} ORDER BY d.draw_date DESC, d.id DESC LIMIT %s",
        params + [limit],
    )
    alloc_map = _draw_allocations([int(r["id"]) for r in rows])
    out = []
    for row in rows:
        amount = _dec(row["amount"]) or _ZERO
        cny = _dec(row["cny_amount"])
        if row["card_id"]:
            owner_kind = "card"
            owner_name = " ".join(x for x in (row["brand"], row["model"]) if x) or None
            mgmt_no = row["card_mgmt_no"]
        elif row["device_id"]:
            owner_kind = "device"
            owner_name = row["device_title"]
            mgmt_no = row["device_mgmt_no"]
        else:
            owner_kind, owner_name, mgmt_no = None, None, None
        out.append({
            "id": row["id"],
            "card_id": row["card_id"],
            "device_id": row["device_id"],
            "owner_kind": owner_kind,
            "owner_name": owner_name,
            "mgmt_no": mgmt_no,
            "category": row["category"],
            "draw_date": _iso(row["draw_date"]),
            "amount": _float(amount),
            "currency": row["currency"],
            "note": row["note"],
            "cny_amount": _float(cny),
            "shortfall": _float(row["shortfall"]),
            "effective_rate": _float(amount / cny) if (cny and cny > 0) else None,
            "allocations": alloc_map.get(int(row["id"]), []),
            "created_at": _iso(row["created_at"]),
        })
    return out


def card_draws(card_id: int) -> List[Dict[str, Any]]:
    return list_draws(card_id=card_id)


def device_draws(device_id: int) -> List[Dict[str, Any]]:
    return list_draws(device_id=device_id)


def summary() -> Dict[str, Any]:
    """池子的总账：进了多少、花了多少、还剩多少，以及剩余部分的人民币成本。

    「剩余的人民币成本」不是「剩余日元 ÷ 今天的牌价」，而是按各批次自己的汇率分别算
    再相加——池子里躺着的钱值多少，取决于它当初是用什么价换进来的。
    """
    injections = list_injections()
    total_in = sum(i["amount"] or 0 for i in injections)
    total_in_cny = sum(i["cny_cost"] or 0 for i in injections)
    incomplete_injections = sum(1 for i in injections if i["fx_rate"] is None)
    remaining = sum(i["remaining_amount"] or 0 for i in injections)
    remaining_cny = sum(i["remaining_cny"] or 0 for i in injections)

    used_row = db.query_one(
        "SELECT COALESCE(SUM(amount), 0) AS jpy, COALESCE(SUM(cny_amount), 0) AS cny, "
        "COALESCE(SUM(shortfall), 0) AS shortfall, COUNT(*) AS n, "
        "SUM(CASE WHEN cny_amount IS NULL THEN 1 ELSE 0 END) AS broken FROM fund_draws"
    ) or {}
    used_jpy = _dec(used_row.get("jpy")) or _ZERO
    used_cny = _dec(used_row.get("cny")) or _ZERO

    return {
        "currency": POOL_CURRENCY,
        "total_injected": round(total_in, 2),
        "total_injected_cny": round(total_in_cny, 2),
        "total_drawn": _float(used_jpy),
        "total_drawn_cny": _float(used_cny),
        "balance": round(remaining, 2),
        "balance_cny": round(remaining_cny, 2),
        "shortfall": _float(used_row.get("shortfall")),
        "draw_count": int(used_row.get("n") or 0),
        "injection_count": len(injections),
        # 池子的平均换汇成本：总日元 ÷ 总人民币。缺汇率的批次没算进人民币，
        # 所以只有全部批次都有汇率时这个数才准，前端用 incomplete 标记提示。
        "avg_rate": round(total_in / total_in_cny, 4) if total_in_cny else None,
        "used_rate": _float(used_jpy / used_cny) if used_cny > 0 else None,
        "incomplete": bool(incomplete_injections or int(used_row.get("broken") or 0)),
        "incomplete_injections": incomplete_injections,
    }
