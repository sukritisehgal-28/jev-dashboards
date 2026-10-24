"""CSV in, live-style dashboard out. Jev makes every decision about the data; code does the maths.

    eval/.venv/bin/python demo/run_demo.py demo/data/acme_payments_export.csv
    eval/.venv/bin/python demo/run_demo.py demo/data/acme_payments_export.csv --offline   # reuse cached decisions, no API calls

One Jev call per column, four typed questions in that call:
  type    Choice  what kind of data is this (same taxonomy and wording as the eval harness)
  role    Choice  sum it, average it, group by it, use it as time, or ignore it
  cents   Noul    is this money written in the smallest currency unit?
  filter  Noul    should totals only count rows where this flag is true?

Code then parses, filters, aggregates and renders demo/out/dashboard.html, including a
Decision Inspector (every Jev answer with probability, latency, cost) and a comparison with
what a rules-based tool and pandas' default type inference would do with the same file.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from dotenv import load_dotenv

from jeveval.labels import COLUMN_TYPES, TASK_INSTRUCTIONS, column_type_options
from jeveval.predictors.jev import ENDPOINT, INPUT_PER_MTOK, MODEL
from jeveval.predictors.prompting import render_state
from jeveval.predictors.rules import RulesPredictor
from jeveval.types import Example

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
N_VALUES = 20  # same as the eval's base condition, so measured accuracy applies
FILTER_MIN_P = 0.8

ROLE_CRITERIA = {
    "sum": "A quantity where adding values across rows is meaningful, such as revenue, refunds, or seats sold.",
    "average": "A quantity where only an average is meaningful, such as a rate, score, duration, or unit price.",
    "group_by": "A label to break results down by, such as plan, country, status, or channel.",
    "time": "The date or time each row happened.",
    "ignore": "An identifier, email, URL, or free text that is not useful to chart.",
}
QUESTIONS = {
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


# ---------- Jev ----------

def ask_jev(http: httpx.Client, col: str, values: list[str]) -> dict:
    body = {"model": MODEL, "state": render_state(Example(col, "", col, tuple(values), "")),
            "questions": QUESTIONS}
    start = time.perf_counter()
    for attempt in range(5):
        r = http.post(ENDPOINT, json=body)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(float(r.headers.get("retry-after", 2**attempt)))
            continue
        break
    r.raise_for_status()
    data = r.json()
    a = data["answers"]
    tokens = int(data.get("usage", {}).get("input_tokens", 0))
    return {
        "type": a["type"]["choice"], "type_p": a["type"]["probabilities"],
        "role": a["role"]["choice"], "role_p": a["role"]["probabilities"],
        "cents": a["cents"]["noul"], "filter": a["filter"]["noul"],
        "latency_ms": (time.perf_counter() - start) * 1000, "input_tokens": tokens,
        "cost_usd": tokens * INPUT_PER_MTOK / 1e6,
    }


def ask_units(http: httpx.Client, df: pd.DataFrame, money_cols: list[str]) -> dict:
    """Second pass with table context: a column alone can't say whether 2900 means $29 or $2,900.

    Seeing all headers and a few whole rows (ch_/cus_ ids, plan names) lets Jev recognize the export.
    """
    rows = df.head(5).to_dict(orient="records")
    body = {"model": MODEL,
            "state": {"columns": list(df.columns), "sample_rows": rows},
            "questions": {f"cents::{c}": {
                "type": "noul",
                "instructions": f"In this table, is the column '{c}' a money amount written in the smallest currency "
                                f"unit, such as cents, so it must be divided by 100 to get the normal amount?",
                "criteria": {"true": "Smallest unit, e.g. 2900 means 29.00.",
                             "false": "Already in normal units, e.g. 2900 means 2,900.00."}} for c in money_cols}}
    start = time.perf_counter()
    r = http.post(ENDPOINT, json=body)
    r.raise_for_status()
    data = r.json()
    tokens = int(data.get("usage", {}).get("input_tokens", 0))
    return {"cents": {c: data["answers"][f"cents::{c}"]["noul"] for c in money_cols},
            "latency_ms": (time.perf_counter() - start) * 1000, "input_tokens": tokens,
            "cost_usd": tokens * INPUT_PER_MTOK / 1e6}


def decide(df: pd.DataFrame, cache_path: Path, offline: bool) -> dict[str, dict]:
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    samples = {}
    for col in df.columns:
        vals = [v for v in df[col].tolist() if v.strip()]
        samples[col] = random.Random(col).sample(vals, min(N_VALUES, len(vals)))
    todo = [c for c in df.columns if c not in cache]
    need_units = "_units" not in cache
    if (todo or need_units) and offline:
        raise SystemExit("--offline but some Jev decisions are not cached yet")
    if todo or need_units:
        load_dotenv(ROOT.parent / "eval" / ".env")
        key = os.environ.get("TYPESAFE_API_KEY")
        if not key:
            raise SystemExit("TYPESAFE_API_KEY missing in eval/.env")
        with httpx.Client(headers={"Authorization": f"Bearer {key}"}, timeout=30) as http:
            if todo:
                t0 = time.perf_counter()
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = dict(zip(todo, pool.map(lambda c: ask_jev(http, c, samples[c]), todo)))
                cache.update(results)
                cache["_meta"] = {"wall_ms": (time.perf_counter() - t0) * 1000, "model": MODEL, "columns": len(todo)}
            money = [c for c in df.columns if cache[c]["type"] == "money"]
            cache["_units"] = ask_units(http, df, money) if money else {"cents": {}, "latency_ms": 0,
                                                                         "input_tokens": 0, "cost_usd": 0}
        cache_path.write_text(json.dumps(cache, indent=2))
    for c, p in cache["_units"]["cents"].items():
        cache[c]["cents_table"] = p
    for col in df.columns:
        cache[col]["sample"] = samples[col]
    return cache


# ---------- parsing (code, not the model) ----------

def parse_datetime(s: pd.Series) -> pd.Series:
    v = s.str.strip()
    digits = v[v != ""]
    if len(digits) and digits.str.fullmatch(r"\d+").all():
        n = digits.str.len().mode()[0]
        if n == 10:
            return pd.to_datetime(pd.to_numeric(v, errors="coerce"), unit="s", utc=True)
        if n == 13:
            return pd.to_datetime(pd.to_numeric(v, errors="coerce"), unit="ms", utc=True)
        if n == 8:
            return pd.to_datetime(v, format="%Y%m%d", errors="coerce", utc=True)
    dayfirst = bool(digits.str.contains(r"^\d{1,2}\.\d{1,2}\.\d{4}").any())
    return pd.to_datetime(v, format="mixed", dayfirst=dayfirst, errors="coerce", utc=True)


def parse_number(s: pd.Series) -> pd.Series:
    def one(x: str) -> float:
        x = x.strip()
        if not x:
            return np.nan
        neg = x.startswith("(") and x.endswith(")") or x.startswith("-")
        x = re.sub(r"[^\d,.\-]", "", x).lstrip("-")
        if re.fullmatch(r"\d{1,3}(\.\d{3})+,\d+|\d+,\d{1,2}", x):  # 1.234,56 style
            x = x.replace(".", "").replace(",", ".")
        x = x.replace(",", "")
        try:
            return -float(x) if neg else float(x)
        except ValueError:
            return np.nan
    return s.map(one).astype(float)


TRUE_WORDS = {"true", "yes", "y", "1", "✓", "✔", "t", "x"}


def parse_bool(s: pd.Series) -> pd.Series:
    return s.str.strip().str.lower().isin(TRUE_WORDS)


# ---------- dashboard spec (code) ----------

def cents_decision(d: dict, c: str, overrides: dict[str, bool]) -> dict:
    """Divide by 100? Confident Jev answers are applied; uncertain ones are applied but flagged for the user."""
    p_col, p_table = d[c]["cents"], d[c].get("cents_table")
    p = p_table if p_table is not None else p_col
    if c in overrides:
        return {"col": c, "divide": overrides[c], "status": "confirmed by you", "p_col": p_col, "p_table": p_table}
    status = "decided by Jev" if p < 0.2 or p > 0.8 else "needs your confirmation"
    return {"col": c, "divide": p >= 0.5, "status": status, "p_col": p_col, "p_table": p_table}


def build_spec(df: pd.DataFrame, d: dict[str, dict], overrides: dict[str, bool]) -> dict:
    cols = [c for c in df.columns]
    units = {c: cents_decision(d, c, overrides) for c in cols if d[c]["type"] == "money"}
    typed = {c: d[c]["type"] for c in cols}
    conf = {c: d[c]["type_p"][typed[c]] for c in cols}

    time_cols = sorted((c for c in cols if typed[c] == "datetime"), key=lambda c: -conf[c])
    time_col = time_cols[0] if time_cols else None
    t = parse_datetime(df[time_col]) if time_col else None

    filters = [c for c in cols if typed[c] == "boolean" and d[c]["filter"] >= FILTER_MIN_P]
    mask = pd.Series(True, index=df.index)
    for c in filters:
        mask &= parse_bool(df[c])

    numeric = {}
    for c in cols:
        if typed[c] in ("money", "count", "measure", "percentage"):
            x = parse_number(df[c])
            if typed[c] == "money" and units[c]["divide"]:
                x = x / 100
            numeric[c] = x
    sums = [c for c in numeric if d[c]["role"] == "sum"]
    avgs = [c for c in numeric if d[c]["role"] == "average"]
    money_sums = sorted((c for c in sums if typed[c] == "money"), key=lambda c: -numeric[c][mask].sum())
    primary = money_sums[0] if money_sums else (sums[0] if sums else None)

    kpis = []
    if primary:
        kpis.append({"label": f"Total {primary}", "value": numeric[primary][mask].sum(), "fmt": "money" if typed[primary] == "money" else "num",
                     "note": f"only rows where {', '.join(filters)} is true" if filters else "all rows"})
    for c in sums:
        if c != primary:
            kpis.append({"label": f"Total {c}", "value": numeric[c][mask].sum(), "fmt": "money" if typed[c] == "money" else "num", "note": ""})
    for c in avgs:
        kpis.append({"label": f"Average {c}", "value": numeric[c].mean(), "fmt": "money" if typed[c] == "money" else "num", "note": ""})
    for c in cols:
        if typed[c] == "boolean" and c not in filters:
            kpis.append({"label": f"Share {c}", "value": parse_bool(df[c]).mean() * 100, "fmt": "pct", "note": ""})
    kpis.append({"label": "Rows", "value": len(df), "fmt": "num", "note": f"{int((~mask).sum())} excluded by filter" if filters else ""})

    charts = []
    if time_col is not None:
        month = t.dt.tz_convert(None).dt.to_period("M")
        complete = month < month.max()  # drop the partial current month
        for c in sums:
            series = numeric[c][mask & complete].groupby(month[mask & complete]).sum().sort_index()
            charts.append({"kind": "line", "title": f"{c} by month", "money": typed[c] == "money",
                           "labels": [str(p) for p in series.index], "values": [round(v, 2) for v in series.values]})
        counts = df[complete].groupby(month[complete]).size().sort_index()
        charts.append({"kind": "line", "title": "rows by month", "money": False,
                       "labels": [str(p) for p in counts.index], "values": counts.tolist()})
    if primary:
        for c in cols:
            if d[c]["role"] == "group_by" and typed[c] in ("category", "boolean") and 2 <= df[c].replace("", np.nan).nunique() <= 12:
                g = numeric[primary][mask].groupby(df[c][mask].replace("", "(blank)")).sum().sort_values(ascending=False)
                charts.append({"kind": "bar", "title": f"{primary} by {c}", "money": typed[primary] == "money",
                               "labels": g.index.tolist(), "values": [round(v, 2) for v in g.values]})
    return {"time_col": time_col, "filters": filters, "primary": primary, "kpis": kpis, "charts": charts,
            "units": list(units.values())}


# ---------- comparison: what simpler tools do ----------

def baselines(path: Path, df: pd.DataFrame, d: dict[str, dict]) -> list[dict]:
    naive = pd.read_csv(path)
    rules, opts = RulesPredictor(), column_type_options()
    rows = []
    for c in df.columns:
        rule_type = rules.predict(Example(c, "", c, tuple(d[c]["sample"]), ""), opts).label
        rows.append({"col": c, "pandas": str(naive[c].dtype), "rules": rule_type, "jev": d[c]["type"],
                     "jev_p": d[c]["type_p"][d[c]["type"]], "sample": d[c]["sample"][:3]})
    return rows


# ---------- HTML ----------

def fmt(v: float, kind: str) -> str:
    if kind == "money":
        return f"${v:,.0f}"
    if kind == "pct":
        return f"{v:.1f}%"
    return f"{v:,.0f}"


def render(path: Path, df: pd.DataFrame, d: dict, spec: dict, base: list[dict]) -> str:
    meta = d.get("_meta", {})
    cols = list(df.columns)
    units = d.get("_units", {"cost_usd": 0, "input_tokens": 0, "latency_ms": 0})
    total_cost = sum(d[c]["cost_usd"] for c in cols) + units["cost_usd"]
    total_tokens = sum(d[c]["input_tokens"] for c in cols) + units["input_tokens"]
    e = html.escape
    pending = [u for u in spec["units"] if u["status"] == "needs your confirmation"]
    confirm_html = "".join(
        f'<div class="confirm"><b>Jev is unsure (p = {u["p_table"] if u["p_table"] is not None else u["p_col"]:.2f}):</b> '
        f'is <code>{e(u["col"])}</code> in cents? Showing it {"divided by 100" if u["divide"] else "as is"} for now. '
        f'Confirm with <code>--confirm {e(u["col"])}=yes</code> or <code>=no</code>.</div>' for u in pending)
    def p2(p: float | None) -> str:
        return "-" if p is None else f"{p:.2f}"

    unit_rows = "".join(
        f"<tr><td><code>{e(u['col'])}</code></td><td>{p2(u['p_col'])}</td><td>{p2(u['p_table'])}</td>"
        f"<td>{'÷ 100' if u['divide'] else 'as is'}</td><td>{e(u['status'])}</td></tr>" for u in spec["units"])
    primary_unit = next((u for u in spec["units"] if u["col"] == spec["primary"]), None)
    unit_sentence = (f"read <code>{e(str(spec['primary']))}</code> as money in cents ({e(primary_unit['status'])})"
                     if primary_unit and primary_unit["divide"] else f"read <code>{e(str(spec['primary']))}</code> as money")

    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-label">{e(k["label"])}</div><div class="kpi-value">{fmt(k["value"], k["fmt"])}</div>'
        f'<div class="kpi-note">{e(k["note"])}</div></div>' for k in spec["kpis"])
    chart_html = "".join(
        f'<div class="card"><h3>{e(ch["title"])}</h3><canvas id="c{i}" height="220"></canvas></div>'
        for i, ch in enumerate(spec["charts"]))

    insp_rows = "".join(
        f"<tr><td><code>{e(c)}</code></td><td class='muted'>{e(' | '.join(d[c]['sample'][:3]))[:70]}</td>"
        f"<td><b>{e(d[c]['type'])}</b> <span class='p'>{d[c]['type_p'][d[c]['type']]:.2f}</span></td>"
        f"<td>{e(d[c]['role'])} <span class='p'>{d[c]['role_p'][d[c]['role']]:.2f}</span></td>"
        f"<td>{'yes' if d[c]['cents'] >= 0.5 else 'no'} <span class='p'>{d[c]['cents']:.2f}</span></td>"
        f"<td>{'yes' if d[c]['filter'] >= FILTER_MIN_P and d[c]['type'] == 'boolean' else '-'} <span class='p'>{d[c]['filter']:.2f}</span></td>"
        f"<td>{d[c]['latency_ms']:.0f} ms</td></tr>" for c in cols)

    naive_total = pd.read_csv(path)[spec["primary"]].sum() if spec["primary"] else 0
    jev_total = next((k["value"] for k in spec["kpis"] if k["label"] == f"Total {spec['primary']}"), 0)
    cmp_rows = "".join(
        f"<tr class='{'diff' if b['rules'] != b['jev'] else ''}'><td><code>{e(b['col'])}</code></td>"
        f"<td class='muted'>{e(' | '.join(b['sample']))[:60]}</td><td>{e(b['pandas'])}</td><td>{e(b['rules'])}</td>"
        f"<td><b>{e(b['jev'])}</b></td></tr>" for b in base)
    n_diff = sum(b["rules"] != b["jev"] for b in base)

    charts_js = json.dumps(spec["charts"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jev Dashboard Demo</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root {{ --bg:#f7f7f5; --card:#fff; --ink:#1d1d1b; --muted:#6b6b66; --line:#e4e3de; --accent:#2f6fde; --warn:#c2410c; --warnbg:#fff4ed; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#141413; --card:#1f1f1d; --ink:#ecebe6; --muted:#a3a29b; --line:#33322f; --accent:#6c9cf0; --warn:#fb923c; --warnbg:#2a1d14; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif; }}
main {{ max-width:1180px; margin:0 auto; padding:28px 16px 60px; }}
h1 {{ font-size:22px; margin:0 0 4px; }} h2 {{ font-size:16px; margin:36px 0 12px; }} h3 {{ font-size:13px; margin:0 0 10px; color:var(--muted); font-weight:600; }}
.sub {{ color:var(--muted); margin:0 0 20px; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }}
.kpi, .card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
.kpi-label {{ color:var(--muted); font-size:12px; }} .kpi-value {{ font-size:24px; font-weight:650; margin-top:2px; }} .kpi-note {{ color:var(--muted); font-size:11.5px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:12px; margin-top:12px; }}
.proof {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
.proof .bad {{ background:var(--warnbg); border-color:var(--warn); }} .big {{ font-size:28px; font-weight:700; }}
table {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); border-radius:10px; overflow:hidden; font-size:13px; }}
th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }} th {{ color:var(--muted); font-weight:600; font-size:12px; }}
tr.diff td {{ background:var(--warnbg); }} .p {{ color:var(--muted); font-size:11.5px; }} .muted {{ color:var(--muted); }}
.scroll {{ overflow-x:auto; }} code {{ font-size:12.5px; }}
.confirm {{ background:var(--warnbg); border:1px solid var(--warn); border-radius:10px; padding:10px 14px; margin-bottom:12px; }}
.stats {{ display:flex; gap:24px; flex-wrap:wrap; color:var(--muted); margin:6px 0 12px; }} .stats b {{ color:var(--ink); }}
@media (max-width:640px) {{ .proof {{ grid-template-columns:1fr; }} }}
</style></head>
<body><main>
<h1>Acme Analytics: revenue dashboard</h1>
<p class="sub">Built automatically from <code>{e(path.name)}</code> ({len(df):,} rows × {len(cols)} columns). Jev decided what every column means; code did the maths.</p>

{confirm_html}
<div class="kpis">{kpi_html}</div>
<div class="grid">{chart_html}</div>

<h2>Why it matters: the same file without Jev</h2>
<div class="proof">
  <div class="card bad"><h3>Naive tool (pandas default inference)</h3>
    <div class="big">{naive_total:,.0f}</div>
    <div class="muted">“Total {e(str(spec['primary']))}”: reads cents as plain numbers and counts failed payments, so revenue is about 100× too high, and <code>{e(str(spec['time_col']))}</code> is just an integer, so there is no timeline.</div></div>
  <div class="card"><h3>With Jev</h3>
    <div class="big">${jev_total:,.0f}</div>
    <div class="muted">Jev {unit_sentence}, read <code>{e(str(spec['time_col']))}</code> as a date, and counted only rows where {e(', '.join(spec['filters']) or 'every row')} is true.</div></div>
</div>
<div class="scroll" style="margin-top:12px"><table><tr><th>column</th><th>sample</th><th>pandas sees</th><th>rules tier</th><th>Jev</th></tr>{cmp_rows}</table></div>
<p class="muted">{n_diff} of {len(cols)} columns where the rules tier and Jev disagree are highlighted.</p>

<h2>Decision Inspector</h2>
<div class="stats"><span><b>{len(cols) + 1}</b> Jev calls: 4 questions per column + 1 table-level units check</span><span><b>{meta.get('wall_ms', 0):,.0f} ms</b> total, in parallel</span>
<span><b>{total_tokens:,}</b> input tokens</span><span><b>${total_cost:.5f}</b> total cost</span><span>model <b>{e(meta.get('model', MODEL))}</b></span></div>
<div class="scroll"><table><tr><th>column</th><th>sample</th><th>type</th><th>role</th><th>in cents?</th><th>filters totals?</th><th>latency</th></tr>{insp_rows}</table></div>
<h3 style="margin-top:16px">Money units: column alone vs whole table</h3>
<div class="scroll"><table><tr><th>column</th><th>p(cents), column only</th><th>p(cents), with table context</th><th>applied</th><th>status</th></tr>{unit_rows}</table></div>
<p class="muted">Numbers after each answer are Jev's probabilities. Unit answers between 0.2 and 0.8 are flagged for the user to confirm.</p>
</main>
<script>
const charts = {charts_js};
const css = getComputedStyle(document.documentElement);
const accent = css.getPropertyValue('--accent').trim(), muted = css.getPropertyValue('--muted').trim(), line = css.getPropertyValue('--line').trim();
charts.forEach((c, i) => new Chart(document.getElementById('c' + i), {{
  type: c.kind === 'line' ? 'line' : 'bar',
  data: {{ labels: c.labels, datasets: [{{ data: c.values, borderColor: accent, backgroundColor: c.kind === 'line' ? 'transparent' : accent, tension: .25, pointRadius: 2 }}] }},
  options: {{ plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: x => (c.money ? '$' : '') + x.parsed.y.toLocaleString(undefined, {{maximumFractionDigits: 0}}) }} }} }},
    scales: {{ x: {{ ticks: {{ color: muted }}, grid: {{ display: false }} }}, y: {{ ticks: {{ color: muted, callback: v => (c.money ? '$' : '') + Number(v).toLocaleString() }}, grid: {{ color: line }} }} }} }}
}}));
</script>
</body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--offline", action="store_true", help="use cached Jev decisions only")
    ap.add_argument("--confirm", action="append", default=[], metavar="COLUMN=yes|no",
                    help="answer an uncertain 'is this in cents?' question yourself")
    args = ap.parse_args()
    overrides = {}
    for item in args.confirm:
        col, _, ans = item.partition("=")
        overrides[col] = ans.strip().lower() in ("yes", "y", "true", "1")
    df = pd.read_csv(args.csv, dtype=str, keep_default_na=False)
    OUT.mkdir(exist_ok=True)
    decisions = decide(df, OUT / f"{args.csv.stem}.decisions.json", args.offline)
    spec = build_spec(df, decisions, overrides)
    page = render(args.csv, df, decisions, spec, baselines(args.csv, df, decisions))
    out = OUT / "dashboard.html"
    out.write_text(page, encoding="utf-8")
    cols = list(df.columns)
    cost = sum(decisions[c]["cost_usd"] for c in cols) + decisions["_units"]["cost_usd"]
    print(f"decisions: {len(cols)} columns + 1 table-level call, ${cost:.5f}")
    for u in spec["units"]:
        print(f"  units {u['col']:16} p(cents) column-only={u['p_col']:.2f} with-table={u['p_table']} -> "
              f"{'÷100' if u['divide'] else 'as is'} ({u['status']})")
    print(f"primary metric: {spec['primary']}, time: {spec['time_col']}, filters: {spec['filters']}")
    for k in spec["kpis"][:3]:
        print(f"  KPI {k['label']}: {fmt(k['value'], k['fmt'])}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
