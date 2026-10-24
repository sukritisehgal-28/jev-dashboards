# Demo: messy CSV to dashboard in one command

```bash
eval/.venv/bin/python demo/make_demo_csv.py                                   # 6,432-row Stripe-style export
eval/.venv/bin/python -I demo/run_demo.py demo/data/acme_payments_export.csv  # needs TYPESAFE_API_KEY in eval/.env
eval/.venv/bin/python -I demo/run_demo.py demo/data/acme_payments_export.csv --offline  # re-render from cached decisions
```

Then open `demo/out/dashboard.html`. The output folder is not committed: generate it with your
own API key.

The sample file is built to trip up naive tools: amounts in cents, Unix timestamps, ✓ flags and
failed payments mixed in. Summing the `amount` column as-is gives 52,508,600; the true paid
revenue is $506,065. The dashboard page shows what pandas' default inference and a rules-based
typer make of each column next to the decisions the app used.

Design note: whether `2900` means $29 or $2,900 is often ambiguous from one column, so unit
questions are asked once per table with the headers and a few full rows. Unit answers between
0.2 and 0.8 are flagged for the user to confirm (`--confirm amount=yes`).
