"""From Jev's decisions to a dashboard spec: KPIs and charts the frontend renders as-is.

All numbers are computed here, in code. The spec is plain JSON.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .parsing import parse_bool, parse_datetime, parse_number

FILTER_MIN_P = 0.8
UNSURE_LO, UNSURE_HI = 0.2, 0.8
MAX_BREAKDOWNS = 4
NUMERIC_TYPES = ("money", "count", "measure", "percentage")


def cents_decision(col: str, d: dict, overrides: dict[str, bool]) -> dict:
    """Divide by 100? Table-context answer wins over column-only; the user's answer wins over both."""
    p_col, p_table = d.get("cents"), d.get("cents_table")
    p = p_table if p_table is not None else p_col
    if col in overrides:
        return {"column": col, "divide": overrides[col], "status": "confirmed", "p_column": p_col, "p_table": p_table}
    status = "decided" if p < UNSURE_LO or p > UNSURE_HI else "needs_confirmation"
    return {"column": col, "divide": p >= 0.5, "status": status, "p_column": p_col, "p_table": p_table}


def _clean(x: float) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 2)


def build_spec(df: pd.DataFrame, decisions: dict[str, dict], overrides: dict[str, bool]) -> dict:
    cols = list(df.columns)
    typed = {c: decisions[c]["type"] for c in cols}
    conf = {c: decisions[c]["type_p"].get(typed[c], 0.0) for c in cols}
    units = {c: cents_decision(c, decisions[c], overrides) for c in cols if typed[c] == "money"}

    time_cols = sorted((c for c in cols if typed[c] == "datetime"), key=lambda c: -conf[c])
    time_col = time_cols[0] if time_cols else None

    filters = [c for c in cols if typed[c] == "boolean" and decisions[c]["filter"] >= FILTER_MIN_P]
    mask = pd.Series(True, index=df.index)
    for c in filters:
        mask &= parse_bool(df[c])

    numeric: dict[str, pd.Series] = {}
    for c in cols:
        if typed[c] in NUMERIC_TYPES:
            x = parse_number(df[c])
            if typed[c] == "money" and units[c]["divide"]:
                x = x / 100
            numeric[c] = x
    sums = [c for c in numeric if decisions[c]["role"] == "sum"]
    avgs = [c for c in numeric if decisions[c]["role"] == "average"]
    money_sums = sorted((c for c in sums if typed[c] == "money"), key=lambda c: -numeric[c][mask].sum())
    primary = money_sums[0] if money_sums else (sums[0] if sums else None)

    def fmt_of(c: str) -> str:
        return {"money": "money", "percentage": "number"}.get(typed[c], "number")

    kpis = []
    if primary:
        kpis.append({"label": f"Total {primary}", "value": _clean(numeric[primary][mask].sum()), "format": fmt_of(primary),
                     "note": f"only rows where {', '.join(filters)} is true" if filters else "all rows", "column": primary})
    for c in sums:
        if c != primary:
            kpis.append({"label": f"Total {c}", "value": _clean(numeric[c][mask].sum()), "format": fmt_of(c), "note": "", "column": c})
    for c in avgs:
        kpis.append({"label": f"Average {c}", "value": _clean(numeric[c].mean()), "format": fmt_of(c), "note": "", "column": c})
    for c in cols:
        if typed[c] == "boolean" and c not in filters:
            kpis.append({"label": f"Share {c}", "value": _clean(parse_bool(df[c]).mean() * 100), "format": "percent", "note": "", "column": c})
    kpis.append({"label": "Rows", "value": len(df), "format": "number",
                 "note": f"{int((~mask).sum())} excluded by filter" if filters else "", "column": None})

    charts = []
    if time_col is not None:
        t = parse_datetime(df[time_col]).dt.tz_convert(None)
        month = t.dt.to_period("M")
        valid = month.notna()
        complete = valid & (month < month[valid].max()) if valid.any() else valid  # drop the partial latest month
        for c in sums:
            m = mask & complete
            s = numeric[c][m].groupby(month[m]).sum().sort_index()
            charts.append({"id": f"{c}-by-month", "kind": "line", "title": f"{c} by month", "format": fmt_of(c),
                           "points": [{"x": str(k), "y": _clean(v)} for k, v in s.items()]})
        counts = df[complete].groupby(month[complete]).size().sort_index()
        charts.append({"id": "rows-by-month", "kind": "line", "title": "rows by month", "format": "number",
                       "points": [{"x": str(k), "y": int(v)} for k, v in counts.items()]})
    if primary:
        n = 0
        for c in cols:
            if n >= MAX_BREAKDOWNS:
                break
            # A filter column is constant after filtering, so a breakdown by it says nothing.
            if c not in filters and decisions[c]["role"] == "group_by" and typed[c] in ("category", "boolean"):
                labels = df[c].replace("", np.nan)
                if not 2 <= labels.nunique() <= 12:
                    continue
                g = numeric[primary][mask].groupby(labels[mask].fillna("(blank)")).sum().sort_values(ascending=False)
                charts.append({"id": f"{primary}-by-{c}", "kind": "bar", "title": f"{primary} by {c}", "format": fmt_of(primary),
                               "points": [{"x": str(k), "y": _clean(v)} for k, v in g.items()]})
                n += 1

    return {"time_column": time_col, "filters": filters, "primary": primary,
            "units": list(units.values()), "kpis": kpis, "charts": charts}
