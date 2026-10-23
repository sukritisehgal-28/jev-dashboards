"""Datasets on disk: storage/<id>/data.csv plus meta.json (source, Jev decisions, user overrides).

A file store keeps v1 simple; Neon replaces it later without changing the API.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, dataset_id: str) -> Path:
        if not dataset_id.isalnum():
            raise KeyError(dataset_id)
        return self.root / dataset_id

    def create(self, name: str, source: dict, df: pd.DataFrame) -> dict:
        dataset_id = secrets.token_hex(6)
        meta = {"id": dataset_id, "name": name, "source": source, "created_at": now(), "updated_at": now(),
                "decisions": {}, "overrides": {}}
        self._dir(dataset_id).mkdir()
        self.save(meta, df)
        return meta

    def save(self, meta: dict, df: pd.DataFrame | None = None) -> None:
        d = self._dir(meta["id"])
        if df is not None:
            df.to_csv(d / "data.csv", index=False)
        (d / "meta.json").write_text(json.dumps(meta, indent=2))

    def meta(self, dataset_id: str) -> dict:
        p = self._dir(dataset_id) / "meta.json"
        if not p.exists():
            raise KeyError(dataset_id)
        return json.loads(p.read_text())

    def data(self, dataset_id: str) -> pd.DataFrame:
        return pd.read_csv(self._dir(dataset_id) / "data.csv", dtype=str, keep_default_na=False)

    def list(self) -> list[dict]:
        metas = [json.loads(p.read_text()) for p in self.root.glob("*/meta.json")]
        return sorted(({k: m[k] for k in ("id", "name", "source", "updated_at")} for m in metas),
                      key=lambda m: m["updated_at"], reverse=True)

    def delete(self, dataset_id: str) -> None:
        d = self._dir(dataset_id)
        for p in d.iterdir():
            p.unlink()
        d.rmdir()
