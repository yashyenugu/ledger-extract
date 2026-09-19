import hashlib
import uuid
from collections.abc import Callable

import psycopg

from app import queue, state_machine, steps

STEP_ORDER = ["preprocess", "extract", "validate"]

ENTER_STATUS: dict[str, str] = {
    "preprocess": "PREPROCESSING",
    "extract": "EXTRACTING",
    "validate": "VALIDATING",
}

RUNNERS: dict[str, Callable[[psycopg.Connection, uuid.UUID], str | None]] = {
    "preprocess": steps.preprocess,
    "extract": steps.extract,
    "validate": steps.validate,
}


def payload_hash(document_id: uuid.UUID, step: str) -> str:
    # Stub steps only depend on document identity, not document content, so
    # the dedupe key is derived from the id rather than re-hashing the file.
    return hashlib.sha256(f"{document_id}:{step}".encode()).hexdigest()


def bootstrap(conn: psycopg.Connection, document_id: uuid.UUID) -> None:
    """Enqueue the first pipeline step for a freshly uploaded document."""
    first_step = STEP_ORDER[0]
    queue.enqueue(conn, document_id, first_step, payload_hash(document_id, first_step))


def run_step(conn: psycopg.Connection, job: dict) -> None:
    step = job["step"]
    document_id = job["document_id"]

    state_machine.transition(conn, document_id, ENTER_STATUS[step])
    final_status = RUNNERS[step](conn, document_id)

    idx = STEP_ORDER.index(step)
    if idx + 1 < len(STEP_ORDER):
        next_step = STEP_ORDER[idx + 1]
        queue.enqueue(
            conn, document_id, next_step, payload_hash(document_id, next_step)
        )
    elif final_status is not None:
        state_machine.transition(conn, document_id, final_status)
