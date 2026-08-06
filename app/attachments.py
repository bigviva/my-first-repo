"""File attachment storage for evidence (photos, 8D reports, inspection data).

Files live on disk under CAT_ATTACHMENTS_DIR (default: data/attachments)
with random hex names — the user-supplied filename is metadata only and
never touches the filesystem, which closes the path-traversal class of
bugs. Metadata lives in the attachments table.

Limits: 25 MB per file, extension allowlist below. Virus scanning is a
deployment concern — hook it between upload and store if required.
"""
import os
import secrets
import sqlite3
from typing import Optional

from fastapi import HTTPException, UploadFile

ATTACH_DIR = os.environ.get(
    "CAT_ATTACHMENTS_DIR",
    os.path.join(os.path.dirname(__file__), "..", "data", "attachments"))

MAX_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "gif", "webp", "heic",
    "xlsx", "xls", "csv", "docx", "doc", "pptx", "ppt", "txt",
    "zip", "msg", "eml",
}


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


async def store(conn: sqlite3.Connection, record_type: str, record_id: int,
                file: UploadFile, uploaded_by: Optional[int]) -> dict:
    ext = _extension(file.filename or "")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"file type '.{ext}' not allowed (allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))})")

    stored_name = f"{secrets.token_hex(16)}.{ext}"
    os.makedirs(ATTACH_DIR, exist_ok=True)
    path = os.path.join(ATTACH_DIR, stored_name)

    size = 0
    with open(path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_BYTES:
                out.close()
                os.remove(path)
                raise HTTPException(status_code=413, detail="file exceeds 25 MB limit")
            out.write(chunk)
    if size == 0:
        os.remove(path)
        raise HTTPException(status_code=400, detail="empty file")

    cur = conn.execute(
        """INSERT INTO attachments (record_type, record_id, filename, content_type,
               size_bytes, stored_name, uploaded_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (record_type, record_id, file.filename or stored_name,
         file.content_type or "application/octet-stream", size, stored_name, uploaded_by))
    return dict(conn.execute(
        "SELECT * FROM attachments WHERE id = ?", (cur.lastrowid,)).fetchone())


def file_path(attachment: dict) -> str:
    return os.path.join(ATTACH_DIR, attachment["stored_name"])


def delete(conn: sqlite3.Connection, attachment: dict) -> None:
    conn.execute("DELETE FROM attachments WHERE id = ?", (attachment["id"],))
    try:
        os.remove(file_path(attachment))
    except FileNotFoundError:
        pass
