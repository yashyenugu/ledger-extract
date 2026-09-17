import os

# Tests run on the host against the Postgres/MinIO ports docker-compose
# publishes to localhost — override the in-container hostnames from .env
# before app.settings is ever imported.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://ledger:ledger@localhost:5433/ledger_extract"
)
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_PUBLIC_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ROOT_USER", "minioadmin")
os.environ.setdefault("MINIO_ROOT_PASSWORD", "minioadmin")
os.environ.setdefault("MINIO_BUCKET", "documents")
os.environ.setdefault("MINIO_USE_SSL", "false")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
