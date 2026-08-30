# -*- coding: utf-8 -*-
"""汇率数据源。

当前只实装 Frankfurter（欧洲央行每日参考汇率）。写成可插拔的 provider 结构，是因为
「换个源」是这个模块最可能发生的变更——真要换成中行牌价或某个付费源，只需要在这里
加一个类并注册进 PROVIDERS，service.py 和上层一行都不用动。

关于 ECB 的两点事实，直接决定了上层怎么用它：

1. **ECB 不直接发布 JPY/CNY**。它发布的是以 EUR 为基准的一篮子汇率，JPY→CNY 是由
   EUR/JPY 和 EUR/CNY 交叉算出来的（Frankfurter 帮我们算好了）。所以这是个参考中间价，
   不等于你实际换汇的成交价——需要精确成本时在卡片上手工覆盖。

2. **只有欧洲的工作日有数据**。周末、元旦、复活节这些日子 ECB 不发牌价。Frankfurter
   对历史日期的处理是「回退到不晚于该日的最近一个发布日」，并在响应的 date 字段里
   告诉你实际用的是哪天。我们把这个实际日期一并存下来，界面上要能看出「你 8/30 买的卡，
   用的是 8/28 的牌价」。
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Dict, Optional, Tuple

import requests

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 12


class ProviderError(RuntimeError):
    """数据源不可用（网络不通、返回格式不对、没有该币种）。"""


class FrankfurterProvider:
    """https://frankfurter.dev —— 欧洲央行数据，免费、无需 API Key、无调用配额。"""

    key = "ecb"
    label = "欧洲央行（Frankfurter）"

    # 主域名挂了还有备用域名。两个域名后面是同一份数据，只是入口不同。
    BASES = ("https://api.frankfurter.dev/v1", "https://api.frankfurter.app")

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout

    def _get(self, path: str, params: Dict[str, str]) -> dict:
        last_error: Optional[Exception] = None
        for base in self.BASES:
            url = f"{base}{path}"
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                log.debug("汇率源 %s 请求失败，尝试下一个入口：%s", url, exc)
        raise ProviderError(f"汇率接口不可用：{last_error}")

    def fetch(self, date: dt.date, base: str, quote: str) -> Tuple[float, dt.date]:
        """取指定日期的 base→quote 汇率。

        返回 ``(汇率, 实际牌价日)``。实际牌价日可能早于请求日期（周末/节假日回退）。
        请求未来日期时 ECB 只能给出最新一天，这里同样如实返回它的日期。
        """
        payload = self._get(f"/{date.isoformat()}", {"base": base, "symbols": quote})
        rates = payload.get("rates") or {}
        if quote not in rates:
            raise ProviderError(f"汇率源未返回 {base}→{quote} 的数据（{date.isoformat()}）")
        try:
            rate = float(rates[quote])
        except (TypeError, ValueError) as exc:
            raise ProviderError(f"汇率值不是数字：{rates[quote]!r}") from exc
        if rate <= 0:
            raise ProviderError(f"汇率值非法：{rate}")

        actual = date
        raw_date = payload.get("date")
        if isinstance(raw_date, str):
            try:
                actual = dt.date.fromisoformat(raw_date)
            except ValueError:
                # 接口换了日期格式也不该让整个请求失败，退回用请求日期
                log.warning("汇率接口返回了无法解析的日期：%r", raw_date)
        return rate, actual

    def fetch_range(
        self, start: dt.date, end: dt.date, base: str, quote: str
    ) -> Dict[dt.date, float]:
        """区间批量拉取，用于「补全最近 N 天」。一次请求顶 N 次，别用循环去打单日接口。"""
        payload = self._get(
            f"/{start.isoformat()}..{end.isoformat()}", {"base": base, "symbols": quote}
        )
        out: Dict[dt.date, float] = {}
        for day, values in (payload.get("rates") or {}).items():
            try:
                out[dt.date.fromisoformat(day)] = float(values[quote])
            except (ValueError, KeyError, TypeError):
                continue
        return out


PROVIDERS = {p.key: p for p in (FrankfurterProvider,)}
DEFAULT_PROVIDER = FrankfurterProvider.key


def get_provider(key: Optional[str] = None) -> FrankfurterProvider:
    cls = PROVIDERS.get((key or DEFAULT_PROVIDER).strip().lower(), FrankfurterProvider)
    return cls()
