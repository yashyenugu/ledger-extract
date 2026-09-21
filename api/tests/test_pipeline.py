import io
import uuid

import psycopg
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app import pipeline, queue, state_machine, worker
from app.db import PSYCOPG_DSN
from app.settings import settings


def _pdf_bytes() -> bytes:
    return f"%PDF-1.4\n% {uuid.uuid4()}\n%%EOF".encode()


def _upload(client: TestClient) -> str:
    res = client.post(
        "/api/documents",
        files={"file": ("receipt.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
    )
    assert res.status_code == 202
    return res.json()["document_id"]


def _raw_connection() -> psycopg.Connection:
    return psycopg.connect(PSYCOPG_DSN, row_factory=dict_row)


def _document_status(conn: psycopg.Connection, document_id: str) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM documents WHERE id = %s", (document_id,))
        return cur.fetchone()["status"]


def test_document_runs_uploaded_to_auto_approved(client: TestClient) -> None:
    document_id = _upload(client)
    doc_uuid = uuid.UUID(document_id)

    with _raw_connection() as conn:
        # preprocess, extract, validate — one job each, scoped to this
        # document so leftover jobs from other tests can't interfere.
        assert worker.run_once(conn, document_id=doc_uuid) is True
        assert worker.run_once(conn, document_id=doc_uuid) is True
        assert worker.run_once(conn, document_id=doc_uuid) is True
        # this document's queue is drained.
        assert worker.run_once(conn, document_id=doc_uuid) is False

        assert _document_status(conn, document_id) == "AUTO_APPROVED"

        with conn.cursor() as cur:
            cur.execute(
                "SELECT page_count FROM documents WHERE id = %s", (document_id,)
            )
            assert cur.fetchone()["page_count"] == 1

            cur.execute(
                "SELECT raw_output FROM extractions WHERE document_id = %s",
                (document_id,),
            )
            assert cur.fetchone()["raw_output"]["vendor"] == "Stub Vendor"

            cur.execute(
                "SELECT status FROM jobs WHERE document_id = %s ORDER BY created_at",
                (document_id,),
            )
            statuses = [row["status"] for row in cur.fetchall()]
            assert statuses == ["done", "done", "done"]


def test_invalid_transition_raises(client: TestClient) -> None:
    document_id = _upload(client)

    with _raw_connection() as conn, conn.transaction():
        try:
            state_machine.transition(conn, uuid.UUID(document_id), "APPROVED")
            raise AssertionError("expected InvalidTransitionError")
        except state_machine.InvalidTransitionError as exc:
            assert exc.from_status == "UPLOADED"
            assert exc.to_status == "APPROVED"


def test_worker_crash_mid_step_resumes_without_duplicating(client: TestClient) -> None:
    document_id = _upload(client)
    doc_uuid = uuid.UUID(document_id)

    # Claim the "preprocess" job but never commit — this stands in for a
    # worker process dying mid-step. Closing the connection drops the
    # uncommitted transaction, so Postgres rolls it back.
    crashing_conn = _raw_connection()
    claimed = queue.claim(crashing_conn, "crashing-worker", document_id=doc_uuid)
    assert claimed is not None
    assert claimed["step"] == "preprocess"
    assert claimed["attempt_count"] == 1
    crashing_conn.close()

    with _raw_connection() as conn:
        # The job must still be pending, as if never claimed.
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, attempt_count FROM jobs WHERE id = %s", (claimed["id"],)
            )
            row = cur.fetchone()
            assert row["status"] == "pending"
            assert row["attempt_count"] == 0

        assert _document_status(conn, document_id) == "UPLOADED"

        # Now actually run it to completion.
        assert worker.run_once(conn, document_id=doc_uuid) is True

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, attempt_count FROM jobs WHERE id = %s", (claimed["id"],)
            )
            row = cur.fetchone()
            assert row["status"] == "done"
            assert row["attempt_count"] == 1

            cur.execute(
                "SELECT page_count FROM documents WHERE id = %s", (document_id,)
            )
            assert cur.fetchone()["page_count"] == 1

        assert _document_status(conn, document_id) == "PREPROCESSING"


def test_step_failure_retries_then_dead_letters(
    client: TestClient, monkeypatch
) -> None:
    document_id = _upload(client)
    doc_uuid = uuid.UUID(document_id)

    call_count = 0

    def _always_fails(conn, doc_id):
        nonlocal call_count
        call_count += 1
        raise queue.TransientStepError("boom")

    monkeypatch.setitem(pipeline.RUNNERS, "preprocess", _always_fails)
    monkeypatch.setattr(settings, "max_job_attempts", 2)
    monkeypatch.setattr(settings, "retry_base_seconds", 0.0)
    monkeypatch.setattr(settings, "retry_cap_seconds", 0.0)

    with _raw_connection() as conn:
        assert worker.run_once(conn, document_id=doc_uuid) is True  # attempt 1: retried
        assert (
            worker.run_once(conn, document_id=doc_uuid) is True
        )  # attempt 2: exhausted

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, attempt_count, failure_reason FROM jobs WHERE document_id = %s",
                (document_id,),
            )
            row = cur.fetchone()
            assert row["status"] == "failed"
            assert row["attempt_count"] == 2
            assert "boom" in row["failure_reason"]

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, failure_reason FROM documents WHERE id = %s",
                (document_id,),
            )
            doc_row = cur.fetchone()
            assert doc_row["status"] == "FAILED"
            assert "boom" in doc_row["failure_reason"]

    assert call_count == 2
