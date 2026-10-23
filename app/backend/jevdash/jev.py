"""Every decision about the data, asked of Jev as typed questions.

Two kinds of call:
- one per column: type, role, cents, filter (column alone is enough for type)
- one per table: is each money column in cents? (units need whole-table context;
  measured in demo/: p 0.44 from the column alone, 0.93 with the table)

Credit safety: every call is checked against a spending cap recorded in a ledger,
and JEV_MOCK=1 answers from the free rules tier instead of the API.
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from jeveval.labels import TASK_INSTRUCTIONS, column_type_options
from jeveval.predictors.jev import ENDPOINT, INPUT_PER_MTOK, MODEL
from jeveval.predictors.prompting import render_state
from jeveval.predictors.rules import RulesPredictor
from jeveval.types import Example

N_VALUES = 20  # matches the eval's base condition, so measured accuracy applies
# Rough upper bound per call, used only to refuse calls that would cross the cap.
EST_COST_PER_CALL = 1500 * INPUT_PER_MTOK / 1e6

ROLE_CRITERIA = {
    "sum": "A quantity where adding values across rows is meaningful, such as revenue, refunds, or seats sold.",
    "average": "A quantity where only an average is meaningful, such as a rate, score, duration, or unit price.",
    "group_by": "A label to break results down by, such as plan, country, status, or channel.",
    "time": "The date or time each row happened.",
    "ignore": "An identifier, email, URL, or free text that is not useful to chart.",
}
COLUMN_QUESTIONS = {
    "type": {"type": "choice", "instructions": TASK_INSTRUCTIONS,
             "criteria": {o.name: o.definition for o in column_type_options()}},
    "role": {"type": "choice",
             "instructions": "This column is part of a business data table that will be summarized on a dashboard. "
                             "Decide how a dashboard should use it.",
             "criteria": ROLE_CRITERIA},
    "cents": {"type": "noul",
              "instructions": "Are these numbers money amounts written in the smallest currency unit, such as cents, "
                              "so they must be divided by 100 to get the normal amount?",
              "criteria": {"true": "Money in cents or another smallest unit.",
                           "false": "Not money, or money already in normal units."}},
    "filter": {"type": "noul",
               "instructions": "Is this a flag saying whether a payment or transaction actually went through, so "
                               "revenue totals should only count rows where it is true?",
               "criteria": {"true": "Only rows where this is true should count toward revenue.",
                            "false": "This flag does not decide whether a row counts toward revenue."}},
}


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Ledger:
    """Running total of Jev spend, persisted so the cap holds across restarts."""

    path: Path
    budget_usd: float

    def __post_init__(self) -> None:
        self.lock = threading.Lock()

    def spent(self) -> float:
        if not self.path.exists():
            return 0.0
        return float(json.loads(self.path.read_text()).get("spent_usd", 0.0))

    def reserve(self, n_calls: int) -> None:
        if self.spent() + n_calls * EST_COST_PER_CALL > self.budget_usd:
            raise BudgetExceeded(
                f"Jev spending cap ${self.budget_usd:.2f} would be exceeded "
                f"(spent ${self.spent():.4f}, {n_calls} calls requested). Raise JEV_BUDGET_USD to continue.")

    def add(self, usd: float, calls: int) -> None:
        with self.lock:
            data = json.loads(self.path.read_text()) if self.path.exists() else {"spent_usd": 0.0, "calls": 0}
            data["spent_usd"] = data.get("spent_usd", 0.0) + usd
            data["calls"] = data.get("calls", 0) + calls
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2))


def sample_values(values: list[str], key: str) -> list[str]:
    present = [v for v in values if str(v).strip()]
    return random.Random(key).sample(present, min(N_VALUES, len(present)))


class JevClient:
    def __init__(self, ledger: Ledger, mock: bool | None = None) -> None:
        self.ledger = ledger
        self.mock = os.environ.get("JEV_MOCK") == "1" if mock is None else mock
        self.http: httpx.Client | None = None
        if not self.mock:
            key = os.environ.get("TYPESAFE_API_KEY")
            if not key:
                raise RuntimeError("TYPESAFE_API_KEY is not set (or run with JEV_MOCK=1)")
            self.http = httpx.Client(headers={"Authorization": f"Bearer {key}"}, timeout=30)

    # ---- API ----

    def _post(self, body: dict) -> tuple[dict, float]:
        assert self.http is not None
        start = time.perf_counter()
        for attempt in range(5):
            r = self.http.post(ENDPOINT, json=body)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(float(r.headers.get("retry-after", 2**attempt)))
                continue
            break
        r.raise_for_status()
        return r.json(), (time.perf_counter() - start) * 1000

    def ask_column(self, header: str, values: list[str]) -> dict:
        sample = sample_values(values, header)
        if self.mock:
            return self._mock_column(header, sample)
        state = render_state(Example(header, "", header, tuple(sample), ""))
        data, ms = self._post({"model": MODEL, "state": state, "questions": COLUMN_QUESTIONS})
        a = data["answers"]
        tokens = int(data.get("usage", {}).get("input_tokens", 0))
        cost = tokens * INPUT_PER_MTOK / 1e6
        self.ledger.add(cost, 1)
        return {
            "sample": sample, "source": MODEL,
            "type": a["type"]["choice"], "type_p": a["type"]["probabilities"],
            "role": a["role"]["choice"], "role_p": a["role"]["probabilities"],
            "cents": a["cents"]["noul"], "filter": a["filter"]["noul"],
            "latency_ms": ms, "input_tokens": tokens, "cost_usd": cost,
        }

    def ask_units(self, columns: list[str], rows: list[dict], money_cols: list[str]) -> dict:
        if not money_cols:
            return {}
        if self.mock:
            return {c: 0.5 for c in money_cols}
        body = {"model": MODEL, "state": {"columns": columns, "sample_rows": rows[:5]},
                "questions": {f"cents::{c}": {
                    "type": "noul",
                    "instructions": f"In this table, is the column '{c}' a money amount written in the smallest "
                                    f"currency unit, such as cents, so it must be divided by 100 to get the normal amount?",
                    "criteria": {"true": "Smallest unit, e.g. 2900 means 29.00.",
                                 "false": "Already in normal units, e.g. 2900 means 2,900.00."}} for c in money_cols}}
        data, _ = self._post(body)
        tokens = int(data.get("usage", {}).get("input_tokens", 0))
        self.ledger.add(tokens * INPUT_PER_MTOK / 1e6, 1)
        return {c: data["answers"][f"cents::{c}"]["noul"] for c in money_cols}

    # ---- free stand-in for development and tests ----

    def _mock_column(self, header: str, sample: list[str]) -> dict:
        opts = column_type_options()
        pred = RulesPredictor().predict(Example(header, "", header, tuple(sample), ""), opts)
        t = pred.label
        role = {"datetime": "time", "category": "group_by", "boolean": "group_by", "money": "sum", "count": "sum",
                "measure": "average", "percentage": "average"}.get(t, "ignore")
        return {
            "sample": sample, "source": "mock (rules tier)",
            "type": t, "type_p": pred.probs,
            "role": role, "role_p": {k: (0.9 if k == role else 0.025) for k in ROLE_CRITERIA},
            "cents": 0.1, "filter": 0.9 if t == "boolean" and header.lower() in ("paid", "is_paid", "success") else 0.1,
            "latency_ms": 0.0, "input_tokens": 0, "cost_usd": 0.0,
        }
