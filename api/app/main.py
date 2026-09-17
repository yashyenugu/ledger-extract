from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from alembic import command
from app.db import check_db
from app.storage import check_storage

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def run_migrations() -> None:
    cfg = Config(str(ALEMBIC_INI))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


app = FastAPI(title="Ledger Extract API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health(response: Response) -> dict:
    db_ok = check_db()
    storage_ok = check_storage()
    status = "ok" if db_ok and storage_ok else "error"
    response.status_code = 200 if status == "ok" else 503
    return {
        "status": status,
        "db": "ok" if db_ok else "error",
        "storage": "ok" if storage_ok else "error",
    }
