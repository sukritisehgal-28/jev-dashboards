"""HTTP API. Run: uvicorn jevdash.api:app --port 8000

Dataset lifecycle: create (upload / Google Sheets / sample) -> Jev decides new columns ->
code builds the dashboard spec. Refreshing a Sheets dataset re-reads the sheet but only asks
Jev about columns it has not seen, so a live dashboard costs nothing per refresh.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from . import sources
from .jev import BudgetExceeded, JevClient, Ledger
from .spec import build_spec
from .store import Store, now

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
SAMPLE_CSV = REPO / "demo" / "data" / "acme_payments_export.csv"

load_dotenv(BACKEND / ".env")
load_dotenv(REPO / "eval" / ".env")  # where the Jev key already lives

app = FastAPI(title="jevdash")


@lru_cache
def store() -> Store:
    return Store(Path(os.environ.get("JEVDASH_STORAGE", BACKEND / "storage")))


@lru_cache
def ledger() -> Ledger:
    return Ledger(store().root / "ledger.json", float(os.environ.get("JEV_BUDGET_USD", "1.00")))


@lru_cache
def jev() -> JevClient:
    return JevClient(ledger())


# ---------- core ----------

def analyze(meta: dict, df: pd.DataFrame) -> None:
    """Ask Jev only about columns without a decision yet; then the table-level units check."""
    decisions = meta["decisions"]
    new = [c for c in df.columns if c not in decisions]
    if not new:
        return
    client = jev()
    if not client.mock:
        ledger().reserve(len(new) + 1)
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        answers = list(pool.map(lambda c: client.ask_column(c, df[c].tolist()), new))
    decisions.update(dict(zip(new, answers)))
    money = [c for c in df.columns if decisions[c]["type"] == "money" and "cents_table" not in decisions[c]]
    rows = df.head(5).to_dict(orient="records")
    for c, p in client.ask_units(list(df.columns), rows, money).items():
        decisions[c]["cents_table"] = p
    meta.setdefault("runs", []).append({"at": now(), "columns": len(new), "wall_ms": (time.perf_counter() - t0) * 1000})


def dashboard(meta: dict, df: pd.DataFrame) -> dict:
    decisions = meta["decisions"]
    cols = list(df.columns)
    return {
        "dataset": {"id": meta["id"], "name": meta["name"], "source": meta["source"], "rows": len(df),
                    "columns": len(cols), "updated_at": meta["updated_at"]},
        "spec": build_spec(df, {c: decisions[c] for c in cols}, meta["overrides"]),
        "decisions": [{"column": c, **decisions[c]} for c in cols],
        "jev": {"calls": len(cols) + (1 if any(decisions[c]["type"] == "money" for c in cols) else 0),
                "cost_usd": sum(decisions[c]["cost_usd"] for c in cols),
                "source": decisions[cols[0]]["source"] if cols else None,
                "last_run": (meta.get("runs") or [None])[-1]},
        "budget": {"spent_usd": ledger().spent(), "cap_usd": ledger().budget_usd},
    }


def create_and_analyze(name: str, source: dict, df: pd.DataFrame) -> dict:
    meta = store().create(name, source, df)
    try:
        analyze(meta, df)
    finally:
        store().save(meta)
    return dashboard(meta, df)


def guarded(fn, *args):
    try:
        return fn(*args)
    except sources.SourceError as e:
        raise HTTPException(400, str(e)) from e
    except BudgetExceeded as e:
        raise HTTPException(402, str(e)) from e
    except KeyError as e:
        raise HTTPException(404, "Dataset not found") from e
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e


# ---------- routes ----------

class SheetIn(BaseModel):
    url: str
    name: str | None = None


class ConfirmIn(BaseModel):
    column: str
    cents: bool


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "mock": os.environ.get("JEV_MOCK") == "1"}


@app.get("/api/budget")
def budget() -> dict:
    return {"spent_usd": ledger().spent(), "cap_usd": ledger().budget_usd}


@app.get("/api/datasets")
def list_datasets() -> list[dict]:
    return store().list()


@app.post("/api/datasets/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    content = await file.read()
    df = guarded(sources.read_upload, file.filename or "upload.csv", content)
    return guarded(create_and_analyze, Path(file.filename or "upload").stem, {"kind": "upload", "filename": file.filename}, df)


@app.post("/api/datasets/sheets")
def from_sheet(body: SheetIn) -> dict:
    df = guarded(sources.fetch_sheet, body.url)
    return guarded(create_and_analyze, body.name or "Google Sheet", {"kind": "sheets", "url": body.url}, df)


@app.post("/api/datasets/sample")
def sample() -> dict:
    df = guarded(sources.read_csv_bytes, SAMPLE_CSV.read_bytes())
    return guarded(create_and_analyze, "Acme payments (sample)", {"kind": "sample", "filename": SAMPLE_CSV.name}, df)


@app.get("/api/datasets/{dataset_id}")
def get_dashboard(dataset_id: str, refresh: bool = False) -> dict:
    def run() -> dict:
        meta = store().meta(dataset_id)
        df = store().data(dataset_id)
        if refresh and meta["source"]["kind"] == "sheets":
            df = sources.fetch_sheet(meta["source"]["url"])
            analyze(meta, df)
            meta["updated_at"] = now()
            store().save(meta, df)
        return dashboard(meta, df)
    return guarded(run)


@app.post("/api/datasets/{dataset_id}/confirm")
def confirm(dataset_id: str, body: ConfirmIn) -> dict:
    def run() -> dict:
        meta = store().meta(dataset_id)
        meta["overrides"][body.column] = body.cents
        store().save(meta)
        return dashboard(meta, store().data(dataset_id))
    return guarded(run)


@app.delete("/api/datasets/{dataset_id}")
def delete(dataset_id: str) -> dict:
    guarded(store().delete, dataset_id)
    return {"deleted": dataset_id}
