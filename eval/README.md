# jeveval: independent evaluation of Jev as a pipeline decision layer

Task 1 of the PRD: **what kind of data does this column hold?** (11 types: id, datetime, money,
count, measure, percentage, category, boolean, email, url, text). Four baseline tiers answer the
same question on the same columns:

| Tier | Predictor | What it is |
| --- | --- | --- |
| 1 | `rules` | Hand-written rules over value statistics. The floor. |
| 2 | `gbm` | Gradient-boosted trees on Sherlock-style features, out-of-fold by source table. |
| 3 | `claude` | `claude-opus-5-5` with structured output, asked for a full probability distribution. |
| 4 | `jev` | TypeSafe `jev-1.13.0` (pinned) via `POST /v1/systemone`, one Choice question. |

## Setup

```bash
cd eval
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env   # then add your keys
.venv/bin/pytest -q
```

## Run

```bash
# synthetic smoke data (pipeline check, not the benchmark)
.venv/bin/python -m jeveval.smoke_data data/smoke.jsonl

# offline tiers, all non-option variants (free)
.venv/bin/jeveval --data data/smoke.jsonl --predictors rules,gbm \
  --variants base,values0,values5,header_drop,header_swap --run-dir runs/smoke

# API tiers: start with a 10-column trial, then remove --limit
.venv/bin/jeveval --data data/smoke.jsonl --predictors claude,jev --variants base --limit 10 --run-dir runs/trial
```

Each run writes `runs/<name>/predictions.jsonl` (cache; re-running resumes), `results.csv`,
`summary.md`, and `figures/reliability.png` + `figures/risk_coverage.png`.

## Starter labeling set (530 real columns)

`data/starter/` holds 530 columns from three CC BY 4.0 datasets ([SOURCES.md](data/starter/SOURCES.md)):
501 from the GitTables column-type benchmark (anonymized headers, so values only) and 29 from
UCI Bank Marketing and Online Retail II. Suggestions come from GitTables' own Schema.org
annotations or from the rules tier, never from a language model, because Claude is a tier under
test.

1. Label `blind.csv` first (60 columns, no suggestions shown).
2. Then `review.csv` (470 columns). `direct` rows are ones where the GitTables annotation and
   the rules tier agree; `review` rows need a real look.
3. Check how much the suggestions sway you: `.venv/bin/python -I -m jeveval.starter agreement`
4. Load only human-confirmed labels with
   `jeveval.data.load_labeled("data/starter/columns.jsonl", "data/starter/blind.csv", "data/starter/review.csv")`.

Known gap: public tables have almost no money (3), percentage (1), boolean (3) or email (2)
columns, the types founder dashboards depend on most. The founder slice fills that gap.

## Founder slice (324 columns, generated)

```bash
.venv/bin/python -I -m jeveval.founder_data data/founder/founder.jsonl
```

Ten export layouts × 3 company sizes: Stripe Charge API objects and Shopify order exports
(column names from their docs), plus CRM, ads, web analytics, KPI sheet, EU invoice, product
event and support-desk layouts modeled on common exports ([LAYOUTS.md](data/founder/LAYOUTS.md)),
and one layout of deliberately misleading headers. Labels come from the generator, never from a
model.

Every hard case is tagged, and `summary.md` reports accuracy per tag: Stripe amounts in cents
(`cents_as_int`), Unix seconds and milliseconds, `20250101`-style dates, `dd.mm.yyyy`,
`1.234,56 €`, `($1,140.12)`, 0-1 fractions as percentages, `00:01:55` durations, ✓/✗ booleans,
`#1001` order IDs, and 30 `misleading_header` columns. Twelve columns a careful person could
dispute are tagged `ambiguous`; the report also shows accuracy without them.

`source` is the layout, so grouped CV and bootstrap never split one export format across folds:
the GBM is always scored on layouts it never trained on.

Rules discipline: the rules tier was written before this slice existed and is now frozen. Tuning
it on these columns would turn test data into training data.

Caveat: values are synthetic. Before quoting results, check a sample against a real export of
your own (kept private; report aggregate metrics only).

## What is measured

- **Accuracy and macro-F1**, with 95% bootstrap CIs that resample whole source tables.
- **Calibration**: ECE (10 equal-width bins, reported because ECE depends on binning),
  multiclass Brier score, log loss, reliability diagram.
- **Selective prediction**: risk-coverage curve, AURC, coverage at 5% error, and the
  cost-minimizing deferral threshold (`--cost-error`, `--cost-defer`). Tied confidences count
  as one operating point, since a threshold cannot split a tie.
- **Paired comparison**: exact McNemar test of every tier against Jev on the same columns.
- **Robustness** (flip rate vs base) under the variants below.
- **Cost and latency**: p50/p95 ms and USD per 1,000 decisions.

| Variant | Tests |
| --- | --- |
| `values0`, `values5`, `values100` | Header only vs 5/20/100 sample values: accuracy vs input-token cost |
| `header_drop`, `header_swap` | H2: does a missing or misleading header override the values? |
| `shuffle1..3` | H3: first-option bias (Jev docs admit it) |
| `codes` | Option names replaced by letters, definitions kept |
| `rotate` | Each option shows another option's name with its own definition: name vs definition (arXiv:2609.26758) |

`rules` and `gbm` ignore option names and order, so the last three variants are skipped for them.

## Caveats (read before quoting any number)

- **Smoke data is synthetic and was written alongside the rules baseline**, so rules look
  better on it than they will on real exports. Results on `data/smoke.jsonl` show the harness
  works; they are not findings.
- **Real results need labeled real tables.** Put CSVs in a folder, label columns in a CSV like
  `data/labels_template.csv`, and load them with `jeveval.data.from_csv_dir`. Target: 500+
  columns from 50+ tables (Kaggle, data.gov, GitTables extracts), with a second labeler on a
  subset for Cohen's kappa.
- Claude's probabilities are generated numbers, not model internals. Jev's come from the API.
  Both are measured, not trusted.
- Prices are hard-coded as of 2026-10 (`predictors/claude.py`, `predictors/jev.py`).

## TypeSafe terms

Checked against the [MCA](https://typesafe.ai/legal/mca) and
[AUP](https://typesafe.ai/legal/acceptable-use-policy) on 2026-10-12 (not legal advice):

- Never train any model on Jev outputs (MCA 2.3(b)). `runs/` is git-ignored; publish metrics,
  not raw outputs.
- No security or prompt-injection testing in the published study (MCA 2.3(g)(2), AUP 3.4/3.7).
- The harness throttles Jev to 20 requests/s, well under the documented 80.
- Get a written OK from TypeSafe before publishing results.

## Next

- Label a real dataset (500+ columns) and rerun every tier on it.
- Sherlock as an additional tier-2 baseline.
- Task 2: mapping columns to the standard data format (same harness, different options).
