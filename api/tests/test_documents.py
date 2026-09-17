import io
import uuid

from fastapi.testclient import TestClient


def _pdf_bytes() -> bytes:
    # A minimal-but-valid-enough PDF header; libmagic identifies PDFs from
    # the leading "%PDF-" signature alone. Salted per call so each test run
    # gets a fresh SHA-256 and never collides with a previous run's rows.
    return f"%PDF-1.4\n% {uuid.uuid4()}\n%%EOF".encode()


def test_upload_happy_path(client: TestClient) -> None:
    content = _pdf_bytes()

    res = client.post(
        "/api/documents",
        files={"file": ("receipt.pdf", io.BytesIO(content), "application/pdf")},
    )

    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "UPLOADED"
    document_id = body["document_id"]

    detail = client.get(f"/api/documents/{document_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "UPLOADED"
    assert detail.json()["mime_type"] == "application/pdf"


def test_duplicate_upload_is_idempotent(client: TestClient) -> None:
    content = _pdf_bytes()

    first = client.post(
        "/api/documents",
        files={"file": ("receipt.pdf", io.BytesIO(content), "application/pdf")},
    )
    assert first.status_code == 202
    first_id = first.json()["document_id"]

    second = client.post(
        "/api/documents",
        files={"file": ("receipt-again.pdf", io.BytesIO(content), "application/pdf")},
    )
    assert second.status_code == 200
    assert second.json()["document_id"] == first_id


def test_mime_rejection(client: TestClient) -> None:
    content = f"just some plain text, not a document {uuid.uuid4()}".encode()

    res = client.post(
        "/api/documents",
        files={"file": ("notes.txt", io.BytesIO(content), "text/plain")},
    )

    assert res.status_code == 415
