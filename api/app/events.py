import asyncio
import uuid
from collections.abc import AsyncIterator

import psycopg
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.db import PSYCOPG_DSN
from app.documents import _fetch_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

KEEPALIVE_SECONDS = 15
TERMINAL_STATES = {"EXPORTED", "FAILED"}


async def _event_stream(document_id: uuid.UUID) -> AsyncIterator[str]:
    doc = _fetch_document(document_id)
    if doc is None:
        return
    yield f"event: status\ndata: {doc['status']}\n\n"
    if doc["status"] in TERMINAL_STATES:
        return

    async with await psycopg.AsyncConnection.connect(PSYCOPG_DSN) as conn:
        await conn.execute("LISTEN document_status")
        await conn.commit()
        notifications = conn.notifies()

        while True:
            try:
                notify = await asyncio.wait_for(
                    anext(notifications), timeout=KEEPALIVE_SECONDS
                )
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue

            doc_id_str, _, status = notify.payload.partition(":")
            if doc_id_str != str(document_id):
                continue
            yield f"event: status\ndata: {status}\n\n"
            if status in TERMINAL_STATES:
                return


@router.get("/{document_id}/events")
async def document_events(document_id: uuid.UUID) -> StreamingResponse:
    if _fetch_document(document_id) is None:
        raise HTTPException(status_code=404, detail="document not found")
    return StreamingResponse(
        _event_stream(document_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
