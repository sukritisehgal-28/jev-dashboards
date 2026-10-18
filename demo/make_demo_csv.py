"""Generate the demo CSV: an 18-month Stripe-style payments export for a fictional SaaS ("Acme Analytics").

    python demo/make_demo_csv.py            # writes demo/data/acme_payments_export.csv

Built to look like what a founder actually downloads, traps included:
- `amount`, `amount_refunded` are integers in cents (Stripe API convention)
- `created` is a Unix timestamp in seconds
- `first_payment` is a ✓ or blank, `paid` / `refunded` are true/false strings
- `receipt_email` and `acquisition_channel` have blanks

The business story inside the data (for the dashboard and, later, the agent):
- steady growth, then a pricing change in March 2026 that spikes refunds
- Scale plan launched in September 2025
- failed payments ~4%, so `paid` matters for revenue totals
"""

from __future__ import annotations

import csv
import random
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).parent / "data" / "acme_payments_export.csv"
START = datetime(2025, 1, 1, tzinfo=timezone.utc)
MONTHS = 18

PLANS = {"Starter": 2900, "Growth": 9900, "Scale": 29900}  # monthly price in cents per seat-bundle
CHANNELS = ("organic", "paid_search", "referral", "product_hunt", "linkedin")
COUNTRIES = ("US", "IN", "GB", "DE", "CA", "AU")
FIRST = ("asha", "liam", "mei", "omar", "sofia", "kenji", "priya", "lucas", "amara", "noah", "ines", "tomas")
DOMAINS = ("gmail.com", "northwind.co", "outlook.com", "startup.dev", "hey.com", "fastmail.com")


def month_start(i: int) -> datetime:
    y, m = divmod(START.month - 1 + i, 12)
    return START.replace(year=START.year + y, month=m + 1)


def rid(rng: random.Random, prefix: str, n: int) -> str:
    return prefix + "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(n))


def main(seed: int = 2026) -> None:
    rng = random.Random(seed)
    customers: list[dict] = []
    rows = []
    for mi in range(MONTHS):
        m0 = month_start(mi)
        # New customers grow ~9%/month from 25.
        for _ in range(int(25 * 1.09**mi + rng.gauss(0, 3))):
            plans = ["Starter", "Growth"] + (["Scale"] if mi >= 8 else [])
            weights = [60, 35] + ([5 + mi] if mi >= 8 else [])
            customers.append({
                "id": rid(rng, "cus_", 14),
                "email": f"{rng.choice(FIRST)}{rng.choice(['', '.', '_'])}{rng.randint(1, 999)}@{rng.choice(DOMAINS)}",
                "plan": rng.choices(plans, weights)[0],
                "country": rng.choices(COUNTRIES, (45, 20, 12, 10, 8, 5))[0],
                "channel": rng.choices(CHANNELS, (35, 25, 15, 10, 15))[0],
                "seats": max(1, int(rng.expovariate(1 / 3))),
                "start": mi,
                "active": True,
            })
        pricing_change = mi == 14  # March 2026
        for c in customers:
            if not c["active"] or c["start"] > mi:
                continue
            if mi > c["start"] and rng.random() < (0.07 if pricing_change else 0.03):
                c["active"] = False
                continue
            amount = PLANS[c["plan"]] * (1 + (c["seats"] - 1) // 5)
            paid = rng.random() > 0.04
            refunded = paid and rng.random() < (0.12 if pricing_change else 0.015)
            when = m0 + timedelta(days=rng.randint(0, 27), seconds=rng.randint(0, 86399))
            rows.append({
                "id": rid(rng, "ch_3", 21),
                "created": int(when.timestamp()),
                "amount": amount,
                "amount_refunded": amount if refunded else 0,
                "currency": "usd",
                "status": "succeeded" if paid else "failed",
                "paid": "true" if paid else "false",
                "refunded": "true" if refunded else "false",
                "customer": c["id"],
                "receipt_email": c["email"] if rng.random() > 0.15 else "",
                "plan": c["plan"],
                "seats": c["seats"],
                "billing_country": c["country"],
                "acquisition_channel": c["channel"] if rng.random() > 0.1 else "",
                "first_payment": "✓" if mi == c["start"] else "",
            })
    rows.sort(key=lambda r: r["created"], reverse=True)  # Stripe exports newest first
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows x {len(rows[0])} columns to {OUT}")


if __name__ == "__main__":
    main()
