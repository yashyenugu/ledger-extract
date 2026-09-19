import json
import uuid

import psycopg

# Hardcoded stand-in for a real SpendRecord (schema lands in a later slice).
STUB_RECORD = {
    "vendor": "Stub Vendor",
    "total_minor": 0,
    "currency": "USD",
    "line_items": [],
}


def preprocess(conn: psycopg.Connection, document_id: uuid.UUID) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE documents SET page_count = %s WHERE id = %s", (1, document_id)
        )


def extract(conn: psycopg.Connection, document_id: uuid.UUID) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO extractions (id, document_id, raw_output)
            VALUES (%s, %s, %s)
            ON CONFLICT (document_id) DO UPDATE SET raw_output = EXCLUDED.raw_output
            """,
            (uuid.uuid4(), document_id, json.dumps(STUB_RECORD)),
        )


def validate(conn: psycopg.Connection, document_id: uuid.UUID) -> str:
    # Stub rule engine: always passes, so every document auto-approves.
    return "AUTO_APPROVED"
