# -*- coding: utf-8 -*-
"""图床 HTTP 客户端。

对接 Image_hosting 的 ``/api/v1`` 端点（Bearer Token 认证，全 JSON）。结构沿用
FreeMarket_Manager 的同名模块，两套系统对着同一个图床说同一种话。

刻意**不做重试**：上传是有副作用的操作，图床侧靠 ``external_key`` 保证幂等，但
「连不上」和「连上了但拒绝」这两类失败需要被调用方区分——批量上传要按单个文件记录
失败原因并继续，而不是被一层重试掩盖成一个笼统的超时。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from src.media import settings

log = logging.getLogger(__name__)


class ImageHostingError(RuntimeError):
    """图床调用失败。``status`` 为 HTTP 状态码；网络层失败时为 None。"""

    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status = status


class ImageHostingClient:
    """一次性客户端：按调用时的配置快照构造，配置改了就重新造一个。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or settings.get()
        self.base_url = cfg["base_url"]
        self.public_base = cfg["public_base"]
        self.project = cfg["project"]
        self.token = cfg["token"]
        self.timeout = cfg["timeout"]
        self.verify_tls = cfg["verify_tls"]
        if not (self.base_url and self.project and self.token):
            raise ImageHostingError(
                "图床未配置完整（地址 / 项目 / Token 三项必填）。请到「系统配置 → 图床」中填写。"
            )

    # ── 内部 ────────────────────────────────────────────────────────── #

    def _url(self, suffix: str) -> str:
        return f"{self.base_url}/api/v1/projects/{quote(self.project, safe='')}{suffix}"

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _request(self, method: str, suffix: str, **kwargs) -> Dict[str, Any]:
        url = self._url(suffix)
        timeout = kwargs.pop("timeout", self.timeout)
        try:
            response = requests.request(
                method, url, headers=self._headers(), timeout=timeout,
                verify=self.verify_tls, **kwargs,
            )
        except requests.RequestException as exc:
            raise ImageHostingError(f"无法连接图床（{url}）：{exc}") from exc
        try:
            payload = response.json()
        except ValueError:
            # 图床异常时可能回 HTML 错误页（反代 502、Flask 的主机校验 400 页）。
            # 原样塞进异常只会刷屏，截断后保留足够定位问题的片段。
            snippet = (response.text or "").strip().replace("\n", " ")[:200]
            raise ImageHostingError(
                f"图床返回了非 JSON 响应（HTTP {response.status_code}）：{snippet}",
                response.status_code,
            )
        if not response.ok:
            raise ImageHostingError(
                str(payload.get("error") or f"图床返回 HTTP {response.status_code}"),
                response.status_code,
            )
        return payload

    # ── 端点 ────────────────────────────────────────────────────────── #

    def ping(self) -> Dict[str, Any]:
        """连接自检，同时带回图床侧的限制（单文件上限、允许的扩展名、缩略图档位）。"""
        return self._request("GET", "/ping")

    def upload(
        self,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        external_key: Optional[str] = None,
        sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        """上传一个文件。带 ``external_key`` 时图床侧幂等：同一个 key 重传返回已有记录。

        视频可能有几十上百 MB，用固定的 30 秒超时会在大文件上必然超时。这里按体积
        放宽：每 2 MB 追加 1 秒，上限 10 分钟。
        """
        data: Dict[str, str] = {}
        if external_key:
            data["external_key"] = external_key
        if sha256:
            data["sha256"] = sha256
        timeout = min(600, max(self.timeout, self.timeout + len(content) // (2 * 1024 * 1024)))
        return self._request(
            "POST", "/images",
            files={"file": (filename, content, content_type)},
            data=data or None,
            timeout=timeout,
        )

    def delete(self, stored_name: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/images/{quote(stored_name, safe='')}")

    def detail(self, stored_name: str) -> Dict[str, Any]:
        return self._request("GET", f"/images/{quote(stored_name, safe='')}")

    def lookup(self, external_keys: List[str]) -> Dict[str, Any]:
        return self._request("POST", "/images/lookup", json={"external_keys": external_keys})

    def fetch_bytes(self, url: str) -> bytes:
        try:
            response = requests.get(url, timeout=self.timeout, verify=self.verify_tls)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ImageHostingError(f"下载图床文件失败（{url}）：{exc}") from exc
        return response.content


def public_url_for(stored_name: str, width: Optional[int] = None) -> str:
    """按当前配置拼出浏览器可访问的 URL。

    用 ``public_base``（不是后端连接用的 ``base_url``）。带 ``width`` 时请求缩略图——
    只对图片有效，视频没有缩略图档位，调用方不要给视频传 width。
    """
    cfg = settings.get()
    base = cfg["public_base"] or cfg["base_url"]
    path = f"/images/{quote(cfg['project'], safe='')}/{quote(stored_name, safe='')}"
    return f"{base}{path}?w={int(width)}" if width else f"{base}{path}"
