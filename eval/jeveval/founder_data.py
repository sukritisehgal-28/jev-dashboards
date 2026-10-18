"""Founder-data slice: SaaS/e-commerce export layouts with the hard cases dashboards hit.

    python -I -m jeveval.founder_data data/founder/founder.jsonl

Why it exists: the 530 public starter columns contain 3 money, 1 percentage,
3 boolean and 2 email columns. Founder dashboards live on exactly those types.

How it is built:
- Each LAYOUT is one export format. Two are documented (Stripe Charge API
  object, Shopify order export); the rest are modeled on common exports and
  marked "modeled" in LAYOUTS.md. Headers vary across instances the way they
  do between companies ("MRR" / "Monthly Recurring Revenue" / "mrr_usd").
- Each layout is generated for INSTANCES companies with different scales.
  `source` is the layout, not the instance, so grouped CV and bootstrap treat
  near-duplicate layouts as one group (no template leakage across folds).
- Labels come from the generator (we know what each column means), not from
  any model. Every hard case carries a tag for per-slice reporting; labels a
  careful human could reasonably dispute also carry "ambiguous".

Caveat: values are synthetic. Layout realism comes from documented formats;
value realism should be checked against a real private export before trusting
results (see README).
"""

from __future__ import annotations

import random
import string
import sys
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .data import save_jsonl
from .types import Example

INSTANCES = 3
ROWS = 60
EPOCH0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

Gen = Callable[[random.Random, int, float], list[str]]  # (rng, rows, scale) -> values


@dataclass
class Col:
    headers: tuple[str, ...]  # one per instance style; cycled
    label: str
    gen: Gen
    tags: tuple[str, ...] = ()
    blank: float = 0.0  # share of empty cells (dropped before sampling, as in real loaders)


@dataclass
class Layout:
    name: str
    provenance: str
    cols: list[Col]
    rows: int = ROWS


# ---------- value helpers ----------

def _when(rng: random.Random, days: int = 600) -> datetime:
    return EPOCH0 + timedelta(seconds=rng.randint(0, days * 86400))


def _amounts(rng, n, scale, lo=9, hi=499):
    return [round(rng.lognormvariate(0, 0.8) * rng.uniform(lo, hi) * scale, 2) for _ in range(n)]


def usd(x: float) -> str:
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


def eu(x: float) -> str:
    s = f"{x:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def hexid(rng, prefix: str, n: int = 14) -> str:
    return prefix + "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(n))


def emails(rng, n, upper=False):
    first = ("asha", "liam", "mei", "omar", "sofia", "kenji", "priya", "lucas", "amara", "noah", "ines", "tomas")
    doms = ("gmail.com", "acme.io", "northwind.co", "outlook.com", "startup.dev", "hey.com")
    out = []
    for _ in range(n):
        e = f"{rng.choice(first)}{rng.choice(['', '.', '_'])}{rng.randint(1, 999)}{'+billing' if rng.random() < 0.05 else ''}@{rng.choice(doms)}"
        out.append(e.upper() if upper and rng.random() < 0.3 else e)
    return out


def g(f) -> Gen:
    """Lift a per-row function f(rng, scale) into a column generator."""
    return lambda rng, n, scale: [f(rng, scale) for _ in range(n)]


def choice(*opts, weights=None) -> Gen:
    return lambda rng, n, scale: rng.choices(opts, weights=weights, k=n)


def mostly_zero(fmt, p_nonzero=0.12) -> Gen:
    return lambda rng, n, scale: [
        fmt(round(rng.uniform(5, 200) * scale, 2)) if rng.random() < p_nonzero else fmt(0.0) for _ in range(n)
    ]


def monthly(fmt) -> Gen:
    """One row per month, oldest first (KPI sheets)."""
    def gen(rng, n, scale):
        start = datetime(2024, 10, 1)
        return [fmt(datetime(start.year + (start.month - 1 + i) // 12, (start.month - 1 + i) % 12 + 1, 1)) for i in range(n)]
    return gen


def mixed_month(rng, n, scale):
    fmts = (lambda d: f"{MONTHS[d.month - 1]} {d.year}", lambda d: d.strftime("%Y-%m"), lambda d: f"{d.month}/1/{d.year}")
    return [rng.choice(fmts)(d) for d in (datetime(2024 + (9 + i) // 12, (9 + i) % 12 + 1, 1) for i in range(n))]


def growth_series(rng, n, scale, start=8000.0, g_=0.06, noise=0.04):
    x, out = start * scale, []
    for _ in range(n):
        x *= 1 + g_ + rng.gauss(0, noise)
        out.append(x)
    return out


# ---------- layouts ----------

STRIPE = Layout("stripe_charges", "documented: docs.stripe.com/api/charges/object", [
    Col(("id",), "id", g(lambda r, s: hexid(r, "ch_3", 21))),
    Col(("amount",), "money", lambda r, n, s: [str(int(x * 100)) for x in _amounts(r, n, s)], ("cents_as_int",)),
    Col(("amount_refunded",), "money", mostly_zero(lambda x: str(int(x * 100))), ("cents_as_int", "mostly_zero")),
    Col(("created",), "datetime", g(lambda r, s: str(int(_when(r).timestamp()))), ("unix_seconds",)),
    Col(("currency",), "category", choice("usd", "eur", "gbp", "inr", weights=(70, 15, 10, 5))),
    Col(("customer",), "id", g(lambda r, s: hexid(r, "cus_", 14)), blank=0.2),
    Col(("paid",), "boolean", choice("true", "false", weights=(93, 7))),
    Col(("refunded",), "boolean", choice("false", "true", weights=(95, 5))),
    Col(("receipt_email",), "email", lambda r, n, s: emails(r, n), blank=0.35),
    Col(("status",), "category", choice("succeeded", "failed", "pending", weights=(90, 8, 2))),
    Col(("description",), "text", choice("Subscription creation", "Subscription update", "Payment for invoice",
                                          "Pro plan (annual)", "Seat add-on", "Invoice 0042 for Sept usage")),
    Col(("outcome.risk_score",), "measure", g(lambda r, s: str(max(0, min(99, int(r.gauss(28, 15)))))),
        ("integer_measure", "ambiguous")),
])

SHOPIFY = Layout("shopify_orders", "documented: help.shopify.com order export columns", [
    Col(("Name",), "id", lambda r, n, s: [f"#{1001 + i}" for i in range(n)], ("hash_prefixed_id",)),
    Col(("Email",), "email", lambda r, n, s: emails(r, n, upper=True)),
    Col(("Financial Status",), "category", choice("paid", "refunded", "partially_refunded", "pending", weights=(85, 5, 4, 6))),
    Col(("Paid at",), "datetime", g(lambda r, s: _when(r).astimezone(timezone(timedelta(hours=-4))).strftime("%Y-%m-%d %H:%M:%S %z")),
        ("tz_offset",), blank=0.06),
    Col(("Accepts Marketing",), "boolean", choice("yes", "no", weights=(40, 60))),
    Col(("Currency",), "category", choice("USD", "CAD", "EUR", weights=(80, 12, 8))),
    Col(("Subtotal",), "money", lambda r, n, s: [f"{x:.2f}" for x in _amounts(r, n, s, 15, 180)], ("no_currency_symbol",)),
    Col(("Shipping",), "money", choice("0.00", "4.99", "9.99", "14.95", weights=(45, 25, 20, 10)), ("no_currency_symbol",)),
    Col(("Taxes",), "money", lambda r, n, s: [f"{x * 0.08:.2f}" for x in _amounts(r, n, s, 15, 180)], ("no_currency_symbol",)),
    Col(("Total",), "money", lambda r, n, s: [f"{x:.2f}" for x in _amounts(r, n, s, 20, 220)], ("no_currency_symbol",)),
    Col(("Discount Code",), "category", choice("WELCOME10", "BFCM25", "FRIENDS", "VIP15"), blank=0.7),
    Col(("Discount Amount",), "money", mostly_zero(lambda x: f"{x:.2f}", 0.3), ("mostly_zero", "no_currency_symbol")),
    Col(("Lineitem quantity",), "count", choice("1", "1", "1", "2", "3", "4", "6")),
    Col(("Lineitem name",), "text", choice("Organic Cotton Tee - Black / M", "Ceramic Pour-Over Set", "Daily Planner 2027",
                                           "Linen Throw Pillow - Sand", "Gift Card $50", "Travel Mug 12oz - Sage")),
    Col(("Lineitem price",), "money", choice("24.00", "48.00", "18.50", "39.95", "50.00", "29.00"), ("no_currency_symbol",)),
    Col(("Lineitem SKU",), "id", g(lambda r, s: f"{r.choice(['TEE', 'MUG', 'PLN', 'PIL'])}-{r.randint(100, 999)}-{r.choice('SMLX')}"), blank=0.1),
    Col(("Billing Country",), "category", choice("US", "CA", "GB", "DE", "AU", weights=(70, 12, 8, 5, 5))),
    Col(("Refunded Amount",), "money", mostly_zero(lambda x: f"{x:.2f}", 0.08), ("mostly_zero", "no_currency_symbol")),
    Col(("Id",), "id", g(lambda r, s: str(r.randint(5_400_000_000_000, 5_499_999_999_999))), ("numeric_id",)),
    Col(("Risk Level",), "category", choice("Low", "Medium", "High", weights=(88, 9, 3))),
    Col(("Source",), "category", choice("web", "pos", "shopify_draft_order", "android", weights=(75, 12, 5, 8))),
])

HUBSPOT = Layout("crm_contacts", "modeled on HubSpot-style contact exports", [
    Col(("Record ID", "Contact ID", "hs_object_id"), "id", g(lambda r, s: str(r.randint(10_000_000, 99_999_999_999))), ("numeric_id",)),
    Col(("First Name", "First name", "firstname"), "text", choice("Asha", "Liam", "Mei", "Omar", "Sofia", "Kenji", "Priya", "Lucas")),
    Col(("Email", "Email address", "email"), "email", lambda r, n, s: emails(r, n)),
    Col(("Lifecycle Stage", "Lifecycle stage", "lifecyclestage"), "category",
        choice("Subscriber", "Lead", "Marketing Qualified Lead", "Sales Qualified Lead", "Opportunity", "Customer")),
    Col(("Lead Status", "Lead status", "hs_lead_status"), "category", choice("New", "Open", "In Progress", "Unqualified", "Connected"), blank=0.3),
    Col(("Create Date", "Created", "createdate"), "datetime", g(lambda r, s: _when(r).strftime("%Y-%m-%d %H:%M"))),
    Col(("Number of Sessions", "Sessions", "hs_analytics_num_visits"), "count", g(lambda r, s: str(int(r.expovariate(1 / 6)) + 1))),
    Col(("Became a Customer Date", "Customer since", "hs_lifecyclestage_customer_date"), "datetime",
        g(lambda r, s: _when(r).strftime("%Y-%m-%d")), ("mostly_blank",), blank=0.8),
    Col(("Annual Revenue", "Company revenue", "annualrevenue"), "money",
        g(lambda r, s: str(r.choice([250_000, 1_000_000, 5_000_000, 12_000_000, 50_000_000]))), ("no_currency_symbol", "round_numbers"), blank=0.5),
    Col(("Number of Employees", "Employees", "numberofemployees"), "count", choice("5", "12", "40", "150", "600", "2500"), blank=0.4),
])

ADS = Layout("ads_campaign_report", "modeled on Google Ads campaign report columns", [
    Col(("Campaign", "Campaign name", "campaign"), "category", choice("Brand - Search", "Competitor - Search", "PMax - Prospecting",
                                                                      "Retargeting - Display", "YouTube - Awareness")),
    Col(("Day", "Date", "date"), "datetime", lambda r, n, s: [(EPOCH0 + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]),
    Col(("Impressions", "Impr.", "impressions"), "count", g(lambda r, s: f"{int(r.lognormvariate(8, 1) * s):,}"), ("thousands_separator",)),
    Col(("Clicks", "Clicks", "clicks"), "count", g(lambda r, s: f"{int(r.lognormvariate(4.5, 1) * s):,}"), ("thousands_separator",)),
    Col(("CTR", "CTR", "ctr"), "percentage", g(lambda r, s: f"{r.uniform(0.4, 9):.2f}%")),
    Col(("Avg. CPC", "Avg. CPC", "avg_cpc"), "money", g(lambda r, s: f"{r.uniform(0.3, 6):.2f}"), ("no_currency_symbol",)),
    Col(("Cost", "Cost", "cost_usd"), "money", g(lambda r, s: f"{r.lognormvariate(5, 1) * s:,.2f}"), ("no_currency_symbol",)),
    Col(("Conversions", "Conv.", "conversions"), "count", g(lambda r, s: f"{r.lognormvariate(1.5, 1):.2f}"),
        ("fractional_count", "ambiguous")),
    Col(("Conv. rate", "Conv. rate", "conv_rate"), "percentage", g(lambda r, s: f"{r.uniform(0.5, 12):.2f}%")),
    Col(("Cost / conv.", "Cost/conv.", "cost_per_conversion"), "money", g(lambda r, s: f"{r.uniform(8, 240):.2f}"), ("no_currency_symbol",)),
])

ANALYTICS = Layout("web_analytics_export", "modeled on GA4-style exploration exports", [
    Col(("Date", "date", "Date"), "datetime", lambda r, n, s: [(EPOCH0 + timedelta(days=i)).strftime("%Y%m%d") for i in range(n)], ("yyyymmdd_int",)),
    Col(("Session source / medium", "sessionSourceMedium", "Source / Medium"), "category",
        choice("google / organic", "(direct) / (none)", "newsletter / email", "linkedin / paid", "producthunt / referral")),
    Col(("Sessions", "sessions", "Sessions"), "count", g(lambda r, s: str(int(r.lognormvariate(5, 0.8) * s)))),
    Col(("Engaged sessions", "engagedSessions", "Engaged sessions"), "count", g(lambda r, s: str(int(r.lognormvariate(4.5, 0.8) * s)))),
    Col(("Engagement rate", "engagementRate", "Engagement rate"), "percentage", g(lambda r, s: f"{r.uniform(0.35, 0.8):.4f}"), ("fraction_pct",)),
    Col(("Average engagement time", "averageEngagementTime", "Avg. engagement time"), "measure",
        g(lambda r, s: f"00:{r.randint(0, 4):02d}:{r.randint(0, 59):02d}"), ("duration_hms",)),
    Col(("Bounce rate", "bounceRate", "Bounce rate"), "percentage", g(lambda r, s: f"{r.uniform(0.2, 0.65):.4f}"), ("fraction_pct",)),
    Col(("Key events", "keyEvents", "Conversions"), "count", g(lambda r, s: f"{r.randint(0, 40)}.00"), ("fractional_count",)),
])

KPI_SHEET = Layout("founder_kpi_sheet", "modeled on a hand-maintained Google Sheets KPI tracker", [
    Col(("Month", "month", "Period"), "datetime", mixed_month, ("mixed_date_formats",)),
    Col(("MRR", "Monthly Recurring Revenue", "mrr_usd"), "money",
        lambda r, n, s: [usd(x) if r.random() < 0.8 else f"{x:.0f}" for x in growth_series(r, n, s)], ("mixed_money_formats",)),
    Col(("New MRR", "New MRR ($)", "new_mrr"), "money", lambda r, n, s: [usd(x) for x in _amounts(r, n, s, 400, 3000)]),
    Col(("Churned MRR", "Churn MRR", "churned_mrr"), "money",
        lambda r, n, s: [f"(${x:,.2f})" for x in _amounts(r, n, s, 100, 900)], ("accounting_negative",)),
    Col(("NRR", "Net Revenue Retention", "nrr"), "percentage", g(lambda r, s: f"{r.uniform(92, 118):.0f}%")),
    Col(("Logo churn", "Customer churn", "logo_churn"), "percentage", g(lambda r, s: f"{r.uniform(0.8, 5.5):.1f}"),
        ("percent_without_sign", "ambiguous")),
    Col(("Customers", "# Customers", "paying_customers"), "count", lambda r, n, s: [str(int(x / 90)) for x in growth_series(r, n, s)]),
    Col(("ARPA", "Avg revenue per account", "arpa"), "money", g(lambda r, s: usd(r.uniform(60, 140) * s))),
    Col(("Net burn", "Burn", "net_burn"), "money", g(lambda r, s: f"-{r.uniform(20_000, 90_000) * s:,.0f}"), ("negative_money", "no_currency_symbol")),
    Col(("Runway (months)", "Runway", "runway_mo"), "measure", g(lambda r, s: f"{r.uniform(6, 30):.1f}")),
    Col(("Hit target?", "On track", "target_hit"), "boolean", choice("✓", "✗", "✓", "✓"), ("symbol_boolean",)),
    Col(("Notes", "Comments", "notes"), "text", choice("Launched annual plans", "Two enterprise pilots closed", "Pricing change mid-month",
                                                       "Holiday dip", "Hired first AE", "Churn from SMB cohort"), blank=0.5),
], rows=24)

EU_INVOICES = Layout("eu_invoices", "modeled on EU invoicing exports (comma decimals, dd.mm.yyyy)", [
    Col(("Invoice No", "Rechnungsnummer", "invoice_no"), "id", lambda r, n, s: [f"RE-2026-{i + 140:04d}" for i in range(n)]),
    Col(("Invoice date", "Datum", "date"), "datetime", g(lambda r, s: _when(r).strftime("%d.%m.%Y")), ("dmy_dots",)),
    Col(("Net amount", "Netto", "net"), "money", lambda r, n, s: [eu(x) for x in _amounts(r, n, s, 80, 2400)], ("eu_decimal",)),
    Col(("VAT rate", "MwSt-Satz", "vat_rate"), "percentage", choice("19 %", "7 %", "0 %", "20 %", "21 %")),
    Col(("VAT amount", "MwSt", "vat"), "money", lambda r, n, s: [f"{eu(x * 0.19)} €" for x in _amounts(r, n, s, 80, 2400)], ("eu_decimal",)),
    Col(("Paid", "Bezahlt", "paid"), "boolean", choice("TRUE", "FALSE", weights=(80, 20))),
    Col(("Customer VAT ID", "USt-IdNr.", "vat_id"), "id", g(lambda r, s: f"{r.choice(['DE', 'FR', 'NL', 'AT'])}{r.randint(100_000_000, 999_999_999)}")),
    Col(("Country", "Land", "country"), "category", choice("Germany", "France", "Netherlands", "Austria", "Spain")),
])

PRODUCT_EVENTS = Layout("product_events", "modeled on Mixpanel/Amplitude-style event exports", [
    Col(("distinct_id", "user_id", "amplitude_id"), "id", g(lambda r, s: str(uuid.UUID(int=r.getrandbits(128), version=4)))),
    Col(("$email", "email", "user_email"), "email", lambda r, n, s: emails(r, n), blank=0.4),
    Col(("event", "event_type", "event_name"), "category", choice("Signed Up", "Created Dashboard", "Connected Source",
                                                                  "Invited Teammate", "Exported CSV", "Upgraded Plan")),
    Col(("time", "event_time", "timestamp"), "datetime", g(lambda r, s: str(int(_when(r).timestamp() * 1000))), ("unix_millis",)),
    Col(("session_length_sec", "session_duration", "duration_s"), "measure", g(lambda r, s: str(int(r.expovariate(1 / 240))))),
    Col(("plan", "plan_tier", "subscription_plan"), "category", choice("free", "starter", "growth", "enterprise", weights=(55, 25, 15, 5))),
    Col(("is_paying", "paying", "is_customer"), "boolean", choice("1", "0", weights=(35, 65))),
    Col(("dashboards_created", "num_dashboards", "dashboards"), "count", g(lambda r, s: str(int(r.expovariate(1 / 3))))),
])

SUPPORT = Layout("support_tickets", "modeled on Zendesk-style ticket exports", [
    Col(("Ticket ID", "Id", "ticket_id"), "id", lambda r, n, s: [str(4810 + i) for i in range(n)], ("sequential_numeric_id",)),
    Col(("Subject", "Title", "subject"), "text", choice("Can't connect Google Sheet", "Chart shows wrong totals", "How do I invite my team?",
                                                        "Refund request", "Dashboard not refreshing", "Export to PDF cuts off legend")),
    Col(("Status", "Ticket status", "status"), "category", choice("new", "open", "pending", "solved", "closed")),
    Col(("Priority", "Priority", "priority"), "category", choice("low", "normal", "high", "urgent", weights=(30, 50, 15, 5)), blank=0.2),
    Col(("Requester email", "Requester", "requester_email"), "email", lambda r, n, s: emails(r, n)),
    Col(("Created at", "Created", "created_at"), "datetime", g(lambda r, s: _when(r).strftime("%Y-%m-%dT%H:%M:%SZ"))),
    Col(("Satisfaction", "CSAT", "satisfaction_rating"), "category", choice("good", "bad", "offered", "unoffered"), ("ambiguous",)),
    Col(("First reply time (hrs)", "First reply (h)", "first_reply_hours"), "measure", g(lambda r, s: f"{r.expovariate(1 / 5):.1f}")),
    Col(("Replies", "Comment count", "replies"), "count", g(lambda r, s: str(r.randint(1, 12)))),
])

LAYOUTS = [STRIPE, SHOPIFY, HUBSPOT, ADS, ANALYTICS, KPI_SHEET, EU_INVOICES, PRODUCT_EVENTS, SUPPORT]

# Header lies: columns whose header names a different type than their values.
# Happens with shifted pastes, renamed exports and reused sheet tabs.
MISLEADING = Layout("misleading_headers", "constructed: real value generators under wrong headers", [
    Col(("revenue", "Revenue", "total_revenue"), "count", g(lambda r, s: str(r.randint(0, 60))), ("misleading_header",)),
    Col(("date", "Date", "signup_date"), "category", choice("Q1", "Q2", "Q3", "Q4"), ("misleading_header",)),
    Col(("email", "Email", "contact_email"), "url", g(lambda r, s: f"https://{r.choice(['acme.io', 'northwind.co'])}/u/{r.randint(1, 999)}"), ("misleading_header",)),
    Col(("user_id", "customer_id", "id"), "email", lambda r, n, s: emails(r, n), ("misleading_header",)),
    Col(("conversion_rate", "CVR", "conv_rate"), "count", g(lambda r, s: str(r.randint(3, 400))), ("misleading_header",)),
    Col(("is_active", "active", "Active?"), "money", g(lambda r, s: usd(r.uniform(10, 900))), ("misleading_header",)),
    Col(("count", "total", "num_users"), "percentage", g(lambda r, s: f"{r.uniform(1, 60):.1f}%"), ("misleading_header",)),
    Col(("price", "amount", "cost"), "boolean", choice("yes", "no"), ("misleading_header",)),
    Col(("created_at", "timestamp", "updated"), "id", g(lambda r, s: hexid(r, "evt_", 16)), ("misleading_header",)),
    Col(("notes", "description", "comment"), "datetime", g(lambda r, s: _when(r).strftime("%Y-%m-%d")), ("misleading_header",)),
])


def build(seed: int = 7) -> list[Example]:
    examples = []
    for layout in [*LAYOUTS, MISLEADING]:
        for inst in range(INSTANCES):
            rng = random.Random(f"{seed}:{layout.name}:{inst}")
            scale = (0.3, 1.0, 4.0)[inst % 3]  # small, mid, larger company
            for col in layout.cols:
                header = col.headers[inst % len(col.headers)]
                values = [v for v in col.gen(rng, layout.rows, scale) if rng.random() >= col.blank]
                values = [v for v in values if v.strip()]
                if not values:
                    continue
                examples.append(Example(
                    id=f"founder::{layout.name}::c{inst}::{header}", source=f"founder:{layout.name}",
                    header=header, values=tuple(values), label=col.label, tags=col.tags,
                ))
    return examples


def write_layout_doc(path: Path) -> None:
    lines = ["# Founder slice layouts", "", "| Layout | Provenance | Columns |", "| --- | --- | --- |"]
    for layout in [*LAYOUTS, MISLEADING]:
        lines.append(f"| {layout.name} | {layout.provenance} | {len(layout.cols)} |")
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/founder/founder.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    examples = build()
    save_jsonl(examples, out)
    write_layout_doc(out.parent / "LAYOUTS.md")
    labels = Counter(e.label for e in examples)
    tags = Counter(t for e in examples for t in e.tags)
    print(f"wrote {len(examples)} columns from {len({e.source for e in examples})} layouts to {out}")
    print("labels:", ", ".join(f"{k} {v}" for k, v in labels.most_common()))
    print("tags:", ", ".join(f"{k} {v}" for k, v in tags.most_common()))
