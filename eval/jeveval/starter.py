"""Build the starter labeling set from the downloaded public datasets.

    python -I -m jeveval.starter build       # writes data/starter/*
    python -I -m jeveval.starter agreement   # after you fill blind.csv

Sources (all CC BY 4.0), extracted under data/raw/:
- GitTables column-type benchmark (zenodo.org/records/5706316): suggestions come
  from its Schema.org annotations through SCHEMA_MAP below. Headers in these
  tables are anonymized, so this slice tests values only.
- UCI Bank Marketing (bank-additional-full.csv) and UCI Online Retail II:
  suggestions come from the rules tier.

No language model writes any suggestion: Claude is one of the tiers under
test, so model-written labels would bias the benchmark toward it.

Labeling protocol:
1. Fill `your_label` in blind.csv first. It shows no suggestions.
2. Then review review.csv, where each row carries a suggestion and a flag:
   `direct` mappings are usually right, `review` ones need a real look.
3. Run `agreement` to see how often you agreed with the hidden suggestions on
   the blind set (Cohen's kappa). That is the measure of suggestion bias.
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

from .labels import COLUMN_TYPES, column_type_options
from .predictors.rules import RulesPredictor
from .types import Example

RAW = Path("data/raw")
OUT = Path("data/starter")
MAX_VALUES = 100
PREVIEW_VALUES = 8
BLIND_SIZE = 60
SEED = 0

# Schema.org annotation -> (our type, flag). Annotations not listed here are
# semantic roles (author, parent, project...) with no single structural type,
# so those columns are left out of the starter set.
SCHEMA_MAP: dict[str, tuple[str, str]] = {
    "id": ("id", "direct"),
    "serial number": ("id", "direct"),
    "order number": ("id", "direct"),
    "url": ("url", "direct"),
    "email": ("email", "direct"),
    "start time": ("datetime", "direct"),
    "end time": ("datetime", "direct"),
    "date issued": ("datetime", "direct"),
    "purchase date": ("datetime", "direct"),
    "time": ("datetime", "review"),
    "price": ("money", "direct"),
    "title": ("text", "review"),
    "description": ("text", "review"),
    "comment": ("text", "review"),
    "abstract": ("text", "review"),
    "message": ("text", "review"),
    "text": ("text", "review"),
    "name": ("text", "review"),
    "status": ("category", "review"),
    "state": ("category", "review"),
    "class": ("category", "review"),
    "category": ("category", "review"),
    "color": ("category", "review"),
    "gender": ("category", "review"),
    "language": ("category", "review"),
    "country": ("category", "review"),
    "city": ("category", "review"),
    "role": ("category", "review"),
    "role name": ("category", "review"),
    "interaction type": ("category", "review"),
    "content type": ("category", "review"),
    "file format": ("category", "review"),
    "action": ("category", "review"),
    "event": ("category", "review"),
    "width": ("measure", "review"),
    "height": ("measure", "review"),
    "depth": ("measure", "review"),
    "size": ("measure", "review"),
    "duration": ("measure", "review"),
    "rating": ("measure", "review"),
    "value": ("measure", "review"),
    "members": ("count", "review"),
    "step": ("count", "review"),
}


def _sample_values(series: pd.Series, rng: random.Random) -> tuple[str, ...]:
    vals = [v for v in series.astype(str).tolist() if v.strip()]
    if len(vals) > MAX_VALUES:
        vals = rng.sample(vals, MAX_VALUES)
    return tuple(vals)


def gittables_columns(rng: random.Random) -> list[tuple[Example, str, str]]:
    gt = pd.read_csv(RAW / "gittables" / "schema_gt.csv")
    tables_dir = RAW / "gittables" / "extracted" / "tables"
    out, skipped = [], Counter()
    frames: dict[str, pd.DataFrame] = {}
    rules, opts = RulesPredictor(), column_type_options()
    for row in gt.itertuples():
        mapped = SCHEMA_MAP.get(row.annotation_label)
        if mapped is None:
            skipped[row.annotation_label] += 1
            continue
        table = row.table_id.removesuffix("_schema")
        if table not in frames:
            frames[table] = pd.read_csv(tables_dir / f"{table}.csv", dtype=str, keep_default_na=False)
        col = f"col{row.target_column}"
        values = _sample_values(frames[table][col], rng)
        if not values:
            skipped["(empty column)"] += 1
            continue
        ex = Example(id=f"gittables::{table}::{col}", source=f"gittables:{table}",
                     header="", values=values, label="")
        # GitTables annotations were matched from the original headers, so they are
        # noisy (a "start time" column can hold elapsed seconds). Mark a row direct
        # only when the value-based rules tier independently agrees.
        label, flag = mapped
        if flag == "direct" and rules.predict(ex, opts).label != label:
            flag = "review"
        out.append((ex, label, f"gittables_schema:{row.annotation_label}|{flag}"))
    print(f"gittables: {len(out)} columns kept; skipped {sum(skipped.values())} "
          f"(top: {', '.join(f'{k} {v}' for k, v in skipped.most_common(6))})")
    return out


def _rules_suggestions(source: str, df: pd.DataFrame, rng: random.Random) -> list[tuple[Example, str, str]]:
    rules, opts, out = RulesPredictor(), column_type_options(), []
    for col in df.columns:
        values = _sample_values(df[col], rng)
        ex = Example(id=f"{source}::{col}", source=source, header=str(col), values=values, label="")
        out.append((ex, rules.predict(ex, opts).label, "rules|review"))
    return out


def uci_columns(rng: random.Random) -> list[tuple[Example, str, str]]:
    bank = pd.read_csv(RAW / "uci_bank/extracted/additional/bank-additional/bank-additional-full.csv",
                       sep=";", dtype=str, keep_default_na=False)
    retail = pd.read_excel(RAW / "uci_retail/extracted/online_retail_II.xlsx", sheet_name=0,
                           nrows=20000, dtype=str).fillna("")
    out = _rules_suggestions("uci_bank", bank, rng) + _rules_suggestions("uci_retail", retail, rng)
    print(f"uci: {len(out)} columns ({bank.shape[1]} bank, {retail.shape[1]} retail)")
    return out


def _preview(values: tuple[str, ...]) -> str:
    return " | ".join(v[:60] for v in values[:PREVIEW_VALUES])


def build() -> None:
    rng = random.Random(SEED)
    rows = gittables_columns(rng) + uci_columns(rng)
    OUT.mkdir(parents=True, exist_ok=True)

    with open(OUT / "columns.jsonl", "w") as f:
        for ex, _, _ in rows:
            f.write(json.dumps({"id": ex.id, "source": ex.source, "header": ex.header,
                                "values": list(ex.values)}) + "\n")

    # Blind set: stratified by suggested type so rare types appear.
    by_type: dict[str, list[int]] = {}
    for i, (_, label, _) in enumerate(rows):
        by_type.setdefault(label, []).append(i)
    blind: set[int] = set()
    pick = random.Random(SEED + 1)
    while len(blind) < min(BLIND_SIZE, len(rows)):
        for idxs in by_type.values():
            remaining = [i for i in idxs if i not in blind]
            if remaining and len(blind) < BLIND_SIZE:
                blind.add(pick.choice(remaining))

    with open(OUT / "blind.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "source", "header", "sample_values", "your_label", "notes"])
        for i in sorted(blind):
            ex = rows[i][0]
            w.writerow([ex.id, ex.source, ex.header, _preview(ex.values), "", ""])
    with open(OUT / ".blind_suggestions.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "suggested_label", "suggested_by"])
        for i in sorted(blind):
            ex, label, by = rows[i]
            w.writerow([ex.id, label, by])
    with open(OUT / "review.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "source", "header", "sample_values", "suggested_label", "suggested_by",
                    "flag", "your_label", "notes"])
        for i, (ex, label, by) in enumerate(rows):
            if i in blind:
                continue
            source, flag = by.split("|")
            w.writerow([ex.id, ex.source, ex.header, _preview(ex.values), label, source, flag, "", ""])

    counts = Counter(label for _, label, _ in rows)
    flags = Counter(by.split("|")[1] for i, (_, _, by) in enumerate(rows) if i not in blind)
    print(f"wrote {len(rows)} columns to {OUT}/ ({len(blind)} blind, {len(rows) - len(blind)} to review: "
          f"{flags['direct']} direct, {flags['review']} need a real look)")
    print("suggested types:", ", ".join(f"{k} {counts.get(k, 0)}" for k in COLUMN_TYPES))


def agreement() -> None:
    from sklearn.metrics import cohen_kappa_score

    mine = {r["id"]: r["your_label"].strip() for r in csv.DictReader(open(OUT / "blind.csv")) if r["your_label"].strip()}
    sugg = {r["id"]: r["suggested_label"] for r in csv.DictReader(open(OUT / ".blind_suggestions.csv"))}
    bad = sorted({v for v in mine.values() if v not in COLUMN_TYPES})
    if bad:
        sys.exit(f"labels not in taxonomy: {bad}")
    ids = [i for i in mine if i in sugg]
    if not ids:
        sys.exit("fill your_label in data/starter/blind.csv first")
    a, b = [mine[i] for i in ids], [sugg[i] for i in ids]
    agree = sum(x == y for x, y in zip(a, b)) / len(ids)
    print(f"blind columns labeled: {len(ids)}")
    print(f"raw agreement with hidden suggestions: {agree:.1%}")
    print(f"Cohen's kappa: {cohen_kappa_score(a, b):.3f}")
    for i in ids:
        if mine[i] != sugg[i]:
            print(f"  disagree {i}: you={mine[i]} suggestion={sugg[i]}")


if __name__ == "__main__":
    {"build": build, "agreement": agreement}[sys.argv[1] if len(sys.argv) > 1 else "build"]()
