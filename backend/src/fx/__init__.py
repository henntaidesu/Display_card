# -*- coding: utf-8 -*-
"""汇率子系统：按**交易发生的那一天**取 JPY→CNY 牌价。"""

from src.fx.service import (  # noqa: F401
    FxError,
    convert,
    get_rate,
    latest,
    refresh_range,
)
