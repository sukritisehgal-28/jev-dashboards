"""Deterministic synthetic founder-style tables for smoke-testing the harness.

NOT the benchmark. Synthetic values are cleaner than real exports, so results
here only show the pipeline works. Real results need labeled public tables
(see data.from_csv_dir and README).

Includes deliberately hard cases: numeric IDs, money without symbols,
percentages as 0-1 fractions, years, 1-5 ratings, and misleading headers.

    python -m jeveval.smoke_data data/smoke.jsonl
"""

from __future__ import annotations

import random
import sys
from datetime import date, datetime, timedelta

from .data import save_jsonl
from .types import Example

N = 50
WORDS = ("billing", "export", "dashboard", "slow", "login", "invoice", "great", "team", "chart",
         "broken", "love", "setup", "sync", "sheet", "error", "support", "fast", "pricing")
FIRST = ("Asha", "Liam", "Mei", "Omar", "Sofia", "Kenji", "Priya", "Lucas", "Amara", "Noah")
LAST = ("Rao", "Smith", "Chen", "Haddad", "Garcia", "Sato", "Iyer", "Silva", "Okafor", "Brown")


def build() -> list[Example]:
    rng = random.Random(42)
    d0 = date(2026, 1, 1)

    def days(i: int) -> date:
        return d0 + timedelta(days=rng.randint(0, 270) if i < 0 else i)

    def ts() -> datetime:
        return datetime(2026, 1, 1) + timedelta(seconds=rng.randint(0, 270 * 86400))

    def sentence(lo: int = 4, hi: int = 12) -> str:
        return " ".join(rng.choice(WORDS) for _ in range(rng.randint(lo, hi))).capitalize() + "."

    def email() -> str:
        return f"{rng.choice(FIRST).lower()}.{rng.choice(LAST).lower()}{rng.randint(1, 99)}@{rng.choice(['gmail.com', 'acme.io', 'startup.co'])}"

    def col(n: int, f) -> list[str]:
        return [str(f(i)) for i in range(n)]

    tables: dict[str, dict[str, tuple[str, list[str]]]] = {
        "stripe_payments": {
            "charge_id": ("id", col(N, lambda i: "ch_" + "".join(rng.choice("0123456789abcdef") for _ in range(14)))),
            "customer_email": ("email", col(N, lambda i: email())),
            "amount": ("money", col(N, lambda i: f"${rng.choice([29, 49, 99, 199]) * rng.randint(1, 3)}.00")),
            "created": ("datetime", col(N, lambda i: ts().strftime("%Y-%m-%dT%H:%M:%SZ"))),
            "status": ("category", col(N, lambda i: rng.choice(["succeeded", "succeeded", "failed", "refunded"]))),
            "refunded": ("boolean", col(N, lambda i: rng.choice(["true", "false", "false"]))),
            "currency": ("category", col(N, lambda i: rng.choice(["usd", "eur", "gbp"]))),
        },
        "hubspot_contacts": {
            "contact_id": ("id", col(N, lambda i: rng.randint(100000, 999999))),
            "email": ("email", col(N, lambda i: email())),
            "lifecycle_stage": ("category", col(N, lambda i: rng.choice(["lead", "mql", "sql", "customer"]))),
            "company_size": ("category", col(N, lambda i: rng.choice(["1-10", "11-50", "51-200", "201-500"]))),
            "website": ("url", col(N, lambda i: f"https://www.{rng.choice(LAST).lower()}{rng.randint(1, 999)}.com")),
            "notes": ("text", col(N, lambda i: sentence())),
            "signup_date": ("datetime", col(N, lambda i: days(-1).strftime("%m/%d/%Y"))),
        },
        "product_events": {
            "event_uuid": ("id", col(N, lambda i: "%08x-%04x-4%03x-a%03x-%012x" % (
                rng.getrandbits(32), rng.getrandbits(16), rng.getrandbits(12), rng.getrandbits(12), rng.getrandbits(48)))),
            "user_id": ("id", col(N, lambda i: rng.choice(range(5000, 5030)))),
            "event_name": ("category", col(N, lambda i: rng.choice(["page_view", "signup", "export_csv", "invite_sent"]))),
            "ts": ("datetime", col(N, lambda i: ts().strftime("%Y-%m-%d %H:%M:%S"))),
            "session_count": ("count", col(N, lambda i: rng.randint(1, 40))),
            "is_mobile": ("boolean", col(N, lambda i: rng.choice(["1", "0"]))),
        },
        "kpi_sheet": {
            "week": ("datetime", col(N, lambda i: (d0 + timedelta(weeks=i)).strftime("%b %d, %Y"))),
            "signups": ("count", col(N, lambda i: rng.randint(20, 400))),
            "mrr": ("money", col(N, lambda i: f"{rng.uniform(5000, 60000):.2f}")),
            "churn_rate": ("percentage", col(N, lambda i: f"{rng.uniform(0.5, 6):.1f}%")),
            "conversion": ("percentage", col(N, lambda i: f"{rng.uniform(0.01, 0.09):.3f}")),
            "active_users": ("count", col(N, lambda i: rng.randint(300, 9000))),
        },
        "marketing_spend": {
            "campaign": ("category", col(N, lambda i: rng.choice(["spring_launch", "retarget_q2", "brand", "webinar"]))),
            "channel": ("category", col(N, lambda i: rng.choice(["google_ads", "linkedin", "meta", "newsletter"]))),
            "spend_usd": ("money", col(N, lambda i: f"{rng.randint(100, 9000):,}.00")),
            "clicks": ("count", col(N, lambda i: rng.randint(10, 5000))),
            "ctr": ("percentage", col(N, lambda i: f"{rng.uniform(0.3, 4.5):.1f}")),
            "landing_page": ("url", col(N, lambda i: f"https://acme.io/{rng.choice(['pricing', 'demo', 'signup', 'blog'])}?utm={rng.randint(1, 99)}")),
        },
        "support_tickets": {
            "ticket_no": ("id", col(N, lambda i: f"T-{10200 + i}")),
            "subject": ("text", col(N, lambda i: sentence(3, 8))),
            "priority": ("category", col(N, lambda i: rng.choice(["low", "medium", "high", "urgent"]))),
            "opened_at": ("datetime", col(N, lambda i: ts().strftime("%Y-%m-%d %H:%M:%S"))),
            "resolved": ("boolean", col(N, lambda i: rng.choice(["yes", "no"]))),
            "csat": ("category", col(N, lambda i: rng.randint(1, 5))),
        },
        "app_users": {
            "uid": ("id", col(N, lambda i: "".join(rng.choice("0123456789abcdef") for _ in range(8)))),
            "name": ("text", col(N, lambda i: f"{rng.choice(FIRST)} {rng.choice(LAST)}")),
            "plan": ("category", col(N, lambda i: rng.choice(["free", "starter", "pro", "enterprise"]))),
            "seats": ("count", col(N, lambda i: rng.randint(1, 60))),
            "is_trial": ("boolean", col(N, lambda i: rng.choice(["True", "False"]))),
            "country": ("category", col(N, lambda i: rng.choice(["IN", "US", "GB", "DE", "BR"]))),
        },
        "survey_responses": {
            "response_id": ("id", col(N, lambda i: 1 + i)),
            "feedback": ("text", col(N, lambda i: sentence(6, 18))),
            "would_recommend": ("boolean", col(N, lambda i: rng.choice(["Y", "N"]))),
            "submitted": ("datetime", col(N, lambda i: days(-1).strftime("%d %b %Y"))),
        },
        "legacy_export": {  # misleading or opaque headers: values must win
            "c1": ("money", col(N, lambda i: f"${rng.uniform(10, 900):.2f}")),
            "val": ("count", col(N, lambda i: rng.randint(0, 300))),
            "col_3": ("email", col(N, lambda i: email())),
            "dt": ("category", col(N, lambda i: rng.choice(["Q1", "Q2", "Q3", "Q4"]))),
            "amt": ("percentage", col(N, lambda i: f"{rng.randint(1, 60)}%")),
            "revenue": ("count", col(N, lambda i: rng.randint(0, 50))),
        },
        "finance_ledger": {
            "invoice_number": ("id", col(N, lambda i: f"INV-2026-{i + 1:04d}")),
            "year": ("datetime", col(N, lambda i: rng.choice(["2024", "2025", "2026"]))),
            "amount_inr": ("money", col(N, lambda i: f"₹{rng.randint(1000, 90000):,}")),
            "discount": ("percentage", col(N, lambda i: f"{rng.choice([0, 5, 10, 15, 20])}%")),
            "paid": ("boolean", col(N, lambda i: rng.choice(["TRUE", "FALSE"]))),
            "memo": ("text", col(N, lambda i: sentence(3, 10))),
        },
    }

    return [
        Example(id=f"{source}::{header}", source=source, header=header, values=tuple(values), label=label)
        for source, cols in tables.items()
        for header, (label, values) in cols.items()
    ]


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "data/smoke.jsonl"
    examples = build()
    save_jsonl(examples, out)
    print(f"wrote {len(examples)} columns from {len({e.source for e in examples})} tables to {out}")
