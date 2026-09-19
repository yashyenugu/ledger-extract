import logging
import uuid

import psycopg

logger = logging.getLogger("app.state_machine")

# Guarded transitions per docs/DESIGN.md §8. FAILED is reachable from any
# non-terminal state (retry exhaustion, dead-letter), so it isn't listed
# per-source below — see `transition()`.
VALID_TRANSITIONS: dict[str, set[str]] = {
    "UPLOADED": {"PREPROCESSING"},
    "PREPROCESSING": {"EXTRACTING"},
    "EXTRACTING": {"VALIDATING"},
    "VALIDATING": {"AUTO_APPROVED", "NEEDS_REVIEW"},
    "NEEDS_REVIEW": {"IN_REVIEW"},
    "IN_REVIEW": {"APPROVED"},
    "AUTO_APPROVED": {"APPROVED"},
    "APPROVED": {"EXPORTED"},
    "EXPORTED": set(),
    "FAILED": set(),
}

TERMINAL_STATES = {"EXPORTED", "FAILED"}


class InvalidTransitionError(Exception):
    def __init__(self, document_id: uuid.UUID, from_status: str, to_status: str):
        self.document_id = document_id
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"document {document_id}: invalid transition {from_status} -> {to_status}"
        )


def transition(
    conn: psycopg.Connection,
    document_id: uuid.UUID,
    to_status: str,
    failure_reason: str | None = None,
) -> str:
    """Move a document to `to_status`, guarded by VALID_TRANSITIONS.

    Must run inside the caller's transaction (no commit here) so the status
    change lands atomically with whatever else the step does. Locks the
    document row for the duration of the caller's transaction to serialize
    concurrent transition attempts.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status FROM documents WHERE id = %s FOR UPDATE", (document_id,)
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"document {document_id} not found")
        from_status = row["status"]

        allowed = to_status == "FAILED" or to_status in VALID_TRANSITIONS.get(
            from_status, set()
        )
        if from_status in TERMINAL_STATES or not allowed:
            raise InvalidTransitionError(document_id, from_status, to_status)

        cur.execute(
            """
            UPDATE documents
            SET status = %s, failure_reason = %s
            WHERE id = %s
            """,
            (to_status, failure_reason, document_id),
        )
        cur.execute(
            "SELECT pg_notify(%s, %s)",
            ("document_status", f"{document_id}:{to_status}"),
        )

    logger.info(
        "document %s transitioned %s -> %s", document_id, from_status, to_status
    )
    return from_status
