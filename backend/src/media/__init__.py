# -*- coding: utf-8 -*-
"""图片/视频存储：文件本体全部走图床，本地只留指针。"""

from src.media.client import (  # noqa: F401
    ImageHostingClient,
    ImageHostingError,
    public_url_for,
)
