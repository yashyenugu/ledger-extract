import random
import uuid

import psycopg

from app.settings import settings

PENDING = "pending"
IN_PROGRESS = "in_progress"
DONE = "done"
FAILED = "failed"


class TransientStepError(Exception):
    """A retryable failure — provider hiccup, timeout, etc."""


class PermanentStepError(Exception):
    """A non-retryable failure — corrupt input, unrecoverable data — goes straight to the DLQ."""


def enqueue(
    conn: psycopg.Connection, document_id: uuid.UUID, step: str, payload_hash: str
) -> None:
    """Insert a pending job, deduped on (document_id, step, payload_hash).

    Re-enqueuing an already-seen (document_id, step, payload_hash) is a no-op,
    which is what makes re-running a completed or in-flight step safe.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO jobs (id, document_id, step, status, payload_hash)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT ON CONSTRAINT uq_jobs_dedupe_key DO NOTHING
            """,
            (uuid.uuid4(), document_id, step, PENDING, payload_hash),
        )


def claim(
    conn: psycopg.Connection, worker_id: str, document_id: uuid.UUID | None = None
) -> dict | None:
    """Claim the oldest available job, or None if there isn't one.

    Must be called inside an open transaction that the caller controls: the
    claiming UPDATE is deliberately left uncommitted so that if the worker
    process dies before finishing the job, the transaction (and the row
    lock `FOR UPDATE SKIP LOCKED` relies on) is rolled back by Postgres and
    the job becomes claimable again exactly as it was — no separate lease
    reaper needed.

    `document_id` restricts claiming to that document's jobs; the worker
    loop never passes it (any available job is fair game), but it lets
    callers — tests, mainly — drive one document's pipeline in isolation.
    """
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT * FROM jobs
            WHERE status = %s AND available_at <= now()
            {"AND document_id = %s" if document_id is not None else ""}
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """,
            (PENDING, document_id) if document_id is not None else (PENDING,),
        )
        job = cur.fetchone()
        if job is None:
            return None

        cur.execute(
            """
            UPDATE jobs
            SET status = %s, locked_at = now(), locked_by = %s,
                attempt_count = attempt_count + 1, updated_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (IN_PROGRESS, worker_id, job["id"]),
        )
        return cur.fetchone()


def mark_done(conn: psycopg.Connection, job_id: uuid.UUID) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE jobs SET status = %s, updated_at = now() WHERE id = %s",
            (DONE, job_id),
        )


def _backoff_seconds(attempt_count: int) -> float:
    base = settings.retry_base_seconds * (2 ** max(attempt_count - 1, 0))
    capped = min(base, settings.retry_cap_seconds)
    return capped + random.uniform(0, capped * 0.25)


def mark_retry_or_fail(conn: psycopg.Connection, job: dict, error: Exception) -> bool:
    """Record a step failure. Returns True if retry was scheduled, False if dead-lettered."""
    dead_letter = isinstance(error, PermanentStepError) or (
        job["attempt_count"] >= settings.max_job_attempts
    )
    with conn.cursor() as cur:
        if dead_letter:
            cur.execute(
                """
                UPDATE jobs
                SET status = %s, failure_reason = %s, updated_at = now()
                WHERE id = %s
                """,
                (FAILED, str(error), job["id"]),
            )
            return False

        delay = _backoff_seconds(job["attempt_count"])
        cur.execute(
            """
            UPDATE jobs
            SET status = %s, available_at = now() + %s * interval '1 second',
                failure_reason = %s, updated_at = now()
            WHERE id = %s
            """,
            (PENDING, delay, str(error), job["id"]),
        )
        return True
