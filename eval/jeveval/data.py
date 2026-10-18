"""Loading labeled columns.

Two sources:
- JSONL of Examples (one object per line: id, source, header, values, label).
- A directory of CSV tables plus a labels CSV (source,file,column,label), for
  labeling real public tables (Kaggle, data.gov, GitTables extracts).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from .labels import COLUMN_TYPES
from .types import Example

MAX_VALUES = 100


def load_jsonl(path: str | Path) -> list[Example]:
    examples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                examples.append(Example(
                    id=d["id"], source=d["source"], header=d["header"],
                    values=tuple(str(v) for v in d["values"]), label=d["label"],
                    tags=tuple(d.get("tags", ())),
                ))
    _validate(examples)
    return examples


def save_jsonl(examples: list[Example], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for e in examples:
            f.write(json.dumps({
                "id": e.id, "source": e.source, "header": e.header,
                "values": list(e.values), "label": e.label, "tags": list(e.tags),
            }, ensure_ascii=False) + "\n")


def from_csv_dir(tables_dir: str | Path, labels_csv: str | Path, seed: int = 0) -> list[Example]:
    """Build Examples from real tables. Values are a seeded sample of non-empty cells."""
    tables_dir = Path(tables_dir)
    frames: dict[str, pd.DataFrame] = {}
    examples = []
    with open(labels_csv) as f:
        for row in csv.DictReader(f):
            file = row["file"]
            if file not in frames:
                frames[file] = pd.read_csv(tables_dir / file, dtype=str, keep_default_na=False)
            col = frames[file][row["column"]]
            vals = [v for v in col.tolist() if v.strip()]
            if len(vals) > MAX_VALUES:
                vals = pd.Series(vals).sample(MAX_VALUES, random_state=seed).tolist()
            examples.append(Example(
                id=f"{row['source']}::{file}::{row['column']}", source=row["source"],
                header=row["column"], values=tuple(vals), label=row["label"],
            ))
    _validate(examples)
    return examples


def load_labeled(columns_jsonl: str | Path, *label_csvs: str | Path) -> list[Example]:
    """Join column values with human labels (`your_label`) from one or more CSVs.

    Rows whose `your_label` is empty are skipped: only human-confirmed labels
    enter the benchmark.
    """
    labels: dict[str, str] = {}
    for path in label_csvs:
        with open(path) as f:
            for row in csv.DictReader(f):
                if row.get("your_label", "").strip():
                    labels[row["id"]] = row["your_label"].strip()
    examples = []
    with open(columns_jsonl) as f:
        for line in f:
            d = json.loads(line)
            if d["id"] in labels:
                examples.append(Example(id=d["id"], source=d["source"], header=d["header"],
                                        values=tuple(d["values"]), label=labels[d["id"]]))
    _validate(examples)
    return examples


def _validate(examples: list[Example]) -> None:
    ids = [e.id for e in examples]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate example ids")
    bad = sorted({e.label for e in examples} - set(COLUMN_TYPES))
    if bad:
        raise ValueError(f"labels not in taxonomy: {bad}")
