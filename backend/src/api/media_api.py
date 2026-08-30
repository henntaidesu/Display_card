# -*- coding: utf-8 -*-
"""显卡图片 / 视频的上传、排序、删除。

文件本体一律走图床，本项目的库里只存指针（stored_name + public_url）。这样做的直接
好处是：这个程序打包成 exe 换机器运行、甚至同时开两份，图片都还在原地。
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src import cards, db
from src.auth import require_auth
from src.media import ImageHostingClient, ImageHostingError
from src.schema import MEDIA_CATEGORIES

log = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["media"], dependencies=[Depends(require_auth)])

# 单次请求的文件数上限。图床侧也有自己的限制，这里先挡一道，免得一次拖 200 个文件
# 进来在内存里全部读完才发现超限。
MAX_FILES_PER_REQUEST = 20

VIDEO_EXTENSIONS = {"mp4", "mov", "webm", "m4v", "mkv", "avi"}


def _kind_of(filename: str, content_type: str) -> str:
    if (content_type or "").lower().startswith("video/"):
        return "video"
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    return "video" if ext in VIDEO_EXTENSIONS else "image"


def _guess_content_type(filename: str, provided: Optional[str]) -> str:
    if provided and provided != "application/octet-stream":
        return provided
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


class ReorderPayload(BaseModel):
    """按前端拖拽后的顺序提交 media id 列表。"""
    media_ids: List[int]


@router.post("/upload")
async def upload(
    card_id: int = Form(...),
    category: str = Form(...),
    files: List[UploadFile] = File(...),
):
    """上传一批文件到某张卡的某个分类。

    逐个文件独立成败：一个失败不影响其余，响应里分别列出成功和失败的项。批量传 10 张
    照片时最后一张格式不对就整批回滚，用户得重新选 10 个文件——这种设计是在惩罚用户。
    """
    if category not in MEDIA_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"未知分类：{category}")
    if not db.query_one("SELECT id FROM cards WHERE id = %s", (card_id,)):
        raise HTTPException(status_code=404, detail="显卡不存在")
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=400, detail=f"一次最多上传 {MAX_FILES_PER_REQUEST} 个文件"
        )

    try:
        client = ImageHostingClient()
    except ImageHostingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 追加到分类末尾，不打乱已有顺序
    base_order = int(db.query_scalar(
        "SELECT COALESCE(MAX(sort_order), -1) AS m FROM card_media "
        "WHERE card_id = %s AND category = %s",
        (card_id, category), default=-1,
    ) or -1) + 1

    uploaded, errors = [], []
    for offset, upload_file in enumerate(files):
        filename = upload_file.filename or f"file_{offset}"
        try:
            content = await upload_file.read()
        finally:
            await upload_file.close()
        if not content:
            errors.append({"filename": filename, "error": "文件为空"})
            continue

        digest = hashlib.sha256(content).hexdigest()
        content_type = _guess_content_type(filename, upload_file.content_type)
        kind = _kind_of(filename, content_type)
        # external_key 让图床侧幂等：同一份内容重复上传不会产生第二个文件。
        # 用「卡 + 分类 + 内容摘要」而不是文件名——手机相册里到处都是 IMG_0001.jpg。
        external_key = f"card{card_id}-{category}-{digest[:32]}"

        try:
            result = client.upload(
                filename=filename,
                content=content,
                content_type=content_type,
                external_key=external_key,
                sha256=digest,
            )
        except ImageHostingError as exc:
            log.warning("上传 %s 到图床失败：%s", filename, exc)
            errors.append({"filename": filename, "error": exc.message})
            continue

        stored_name = result.get("stored_name") or result.get("filename") or ""
        public_url = result.get("url") or ""
        if not stored_name or not public_url:
            errors.append({"filename": filename, "error": "图床未返回存储名或访问地址"})
            continue

        media_id = db.insert(
            "INSERT INTO card_media "
            "(card_id, category, kind, stored_name, public_url, filename, mime_type, "
            " size_bytes, sort_order) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (card_id, category, kind, stored_name, public_url, filename[:255],
             content_type[:128], len(content), base_order + offset),
        )
        uploaded.append({
            "id": media_id, "card_id": card_id, "category": category, "kind": kind,
            "stored_name": stored_name, "public_url": public_url, "filename": filename,
            "mime_type": content_type, "size_bytes": len(content),
            "sort_order": base_order + offset,
        })

    return {"uploaded": uploaded, "errors": errors}


@router.get("/card/{card_id}")
def list_for_card(card_id: int):
    grouped = {c: [] for c in MEDIA_CATEGORIES}
    for item in cards.load_media([card_id]).get(card_id, []):
        grouped.setdefault(item["category"], []).append(item)
    return grouped


@router.put("/reorder")
def reorder(payload: ReorderPayload):
    """按传入顺序重排。一次事务写完，不会出现「排到一半」的中间态。"""
    if not payload.media_ids:
        return {"ok": True, "updated": 0}
    with db.transaction() as cur:
        for order, media_id in enumerate(payload.media_ids):
            cur.execute("UPDATE card_media SET sort_order = %s WHERE id = %s", (order, media_id))
    return {"ok": True, "updated": len(payload.media_ids)}


@router.delete("/{media_id}")
def delete_media(media_id: int, purge: bool = True):
    """删除一个文件。``purge=true``（默认）连图床上的本体一起删。

    这里默认删本体，和删整张卡时的默认相反：删单个文件是用户对着那张图点的删除，
    意图明确；删卡是一次波及几十个文件的操作，误删代价大得多。
    """
    row = db.query_one("SELECT id, stored_name FROM card_media WHERE id = %s", (media_id,))
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")

    purged = False
    if purge:
        try:
            ImageHostingClient().delete(row["stored_name"])
            purged = True
        except ImageHostingError as exc:
            # 图床上删不掉也要把本地记录删掉：否则界面上一直挂着一个点不开的坏链接，
            # 用户反复点删除反复失败。图床上留个孤儿文件是可接受的代价。
            log.warning("删除图床文件 %s 失败，仅移除本地记录：%s", row["stored_name"], exc)

    db.execute("DELETE FROM card_media WHERE id = %s", (media_id,))
    return {"ok": True, "purged": purged}
