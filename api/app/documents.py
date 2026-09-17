import hashlib
import uuid
from datetime import datetime

import magic
import psycopg
from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel

from app import storage
from app.db import get_connection
from app.settings import settings

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    sha256: str
    mime_type: str
    page_count: int | None
    source: str | None
    status: str
    failure_reason: str | None
    created_at: datetime


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int


class UploadResult(BaseModel):
    document_id: uuid.UUID
    status: str


def _find_by_sha256(sha256_hex: str) -> dict | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM documents WHERE sha256 = %s", (sha256_hex,))
        return cur.fetchone()


def _insert_document(
    document_id: uuid.UUID,
    filename: str,
    sha256_hex: str,
    storage_uri: str,
    mime_type: str,
    source: str,
    status: str,
) -> dict:
    with get_connection() as conn, conn.cursor() as cur:
        try:
            cur.execute(
                """
                INSERT INTO documents
                    (id, filename, sha256, storage_uri, mime_type, source, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    document_id,
                    filename,
                    sha256_hex,
                    storage_uri,
                    mime_type,
                    source,
                    status,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return row
        except psycopg.errors.UniqueViolation:
            # Lost a race with a concurrent upload of the same file.
            conn.rollback()
            existing = _find_by_sha256(sha256_hex)
            assert existing is not None
            return existing


def _fetch_document(document_id: uuid.UUID) -> dict | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM documents WHERE id = %s", (document_id,))
        return cur.fetchone()


def _fetch_documents(limit: int, offset: int) -> tuple[list[dict], int]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS total FROM documents")
        total = cur.fetchone()["total"]
        cur.execute(
            """
            SELECT * FROM documents
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        return cur.fetchall(), total


@router.post("", response_model=UploadResult)
async def upload_document(
    response: Response, file: UploadFile = File(...)  # noqa: B008
) -> UploadResult:
    hasher = hashlib.sha256()
    size = 0
    head = b""

    while chunk := await file.read(CHUNK_SIZE):
        if not head:
            head = chunk
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413, detail="file exceeds the 20MB upload limit"
            )
        hasher.update(chunk)

    if size == 0:
        raise HTTPException(status_code=400, detail="empty file")

    detected_mime = magic.from_buffer(head, mime=True)
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415, detail=f"unsupported file type: {detected_mime}"
        )

    sha256_hex = hasher.hexdigest()

    existing = _find_by_sha256(sha256_hex)
    if existing is not None:
        response.status_code = 200
        return UploadResult(document_id=existing["id"], status=existing["status"])

    await file.seek(0)
    ext = ALLOWED_MIME_TYPES[detected_mime]
    key = f"documents/{sha256_hex}{ext}"
    storage.put(key, file.file, size, detected_mime)

    row = _insert_document(
        document_id=uuid.uuid4(),
        filename=file.filename or key,
        sha256_hex=sha256_hex,
        storage_uri=f"s3://{settings.minio_bucket}/{key}",
        mime_type=detected_mime,
        source="upload",
        status="UPLOADED",
    )

    response.status_code = 202
    return UploadResult(document_id=row["id"], status=row["status"])


@router.get("", response_model=DocumentListOut)
def list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DocumentListOut:
    items, total = _fetch_documents(limit, offset)
    return DocumentListOut(items=[DocumentOut(**item) for item in items], total=total)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID) -> DocumentOut:
    row = _fetch_document(document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    return DocumentOut(**row)
