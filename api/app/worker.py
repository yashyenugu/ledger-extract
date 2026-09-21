import logging
import os
import time
import uuid

import psycopg
from psycopg.rows import dict_row

from app import pipeline, queue, state_machine
from app.db import PSYCOPG_DSN
from app.settings import settings

logger = logging.getLogger("app.worker")

WORKER_ID = f"{os.uname().nodename}-{os.getpid()}"


def run_once(
    conn: psycopg.Connection,
    worker_id: str = WORKER_ID,
    document_id: uuid.UUID | None = None,
) -> bool:
    """Claim and run a single job. Returns False if there was none to claim.

    Claim, step execution, and completion all happen inside one transaction
    (with the step itself wrapped in a savepoint) so that a crash anywhere
    before the final commit leaves nothing behind — the job simply becomes
    claimable again. A step failure rolls back only to the savepoint, so the
    retry/dead-letter bookkeeping in `queue.mark_retry_or_fail` still commits.
    """
    with conn.transaction():
        job = queue.claim(conn, worker_id, document_id=document_id)
        if job is None:
            return False

        try:
            with conn.transaction():
                pipeline.run_step(conn, job)
                queue.mark_done(conn, job["id"])
        except Exception as exc:
            logger.exception(
                "job %s (document %s, step %s) failed",
                job["id"],
                job["document_id"],
                job["step"],
            )
            retried = queue.mark_retry_or_fail(conn, job, exc)
            if not retried:
                state_machine.transition(
                    conn, job["document_id"], "FAILED", failure_reason=str(exc)
                )

    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info(
        "worker %s starting, polling every %ss",
        WORKER_ID,
        settings.worker_poll_interval_seconds,
    )
    with psycopg.connect(PSYCOPG_DSN, row_factory=dict_row) as conn:
        while True:
            processed = run_once(conn)
            if not processed:
                time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()
