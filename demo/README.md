# Demo: messy CSV to dashboard, with Jev making the decisions

```bash
eval/.venv/bin/python demo/make_demo_csv.py                                   # 6,432-row Stripe-style export
eval/.venv/bin/python -I demo/run_demo.py demo/data/acme_payments_export.csv  # ~16 Jev calls, < $0.001
eval/.venv/bin/python -I demo/run_demo.py demo/data/acme_payments_export.csv --offline  # re-render, no API calls
```

Open `demo/out/dashboard.html` (or the `demo-dashboard` preview in `.claude/launch.json`).

What it proves, on a file with amounts in cents, Unix timestamps, ✓ flags and failed payments:

| | Naive (pandas) | Rules tier | Jev |
| --- | --- | --- | --- |
| Total revenue | 52,508,600 (cents, failed payments included) | | **$506,065** (matches ground truth) |
| `created` (Unix seconds) | int64 | count | **datetime** |
| `first_payment` (✓ / blank) | str | category | **boolean** |
| `currency` (usd) | str | money | **category** |

Design finding: asked about one column alone, Jev was unsure whether `amount` is in cents
(p = 0.44). Given the whole table (headers plus five rows), it was confident (p = 0.93). Unit
questions need table context; type questions don't. Answers between 0.2 and 0.8 are flagged on
the dashboard for the user to confirm (`--confirm amount=yes`).
