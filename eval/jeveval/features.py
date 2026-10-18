"""Hand-built column features shared by the rules baseline and the GBM baseline.

These follow the spirit of Sherlock (Hulsebos et al., KDD 2019): character
and value statistics plus a few header keyword flags.
"""

from __future__ import annotations

import re
from datetime import datetime

import numpy as np

from .types import Example

_NUM = re.compile(r"^[-+]?[$€£₹]?\s?[-+]?\d{1,3}(,\d{3})*(\.\d+)?$|^[-+]?[$€£₹]?\s?\d+(\.\d+)?$")
_INT = re.compile(r"^[-+]?\d+$")
_CURRENCY = re.compile(r"[$€£₹]|\b(usd|eur|gbp|inr)\b", re.I)
_PCT = re.compile(r"%\s*$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
_URL = re.compile(r"^(https?://|www\.)\S+$", re.I)
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_BOOL = {"true", "false", "yes", "no", "y", "n", "t", "f", "0", "1"}
_DATE_FORMATS = (
    "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%b %d, %Y", "%d %b %Y", "%Y/%m/%d",
)

HEADER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "kw_id": ("id", "uuid", "key", "number", "no", "num"),
    "kw_date": ("date", "time", "at", "day", "created", "updated", "ts", "timestamp"),
    "kw_money": ("amount", "amt", "price", "cost", "revenue", "mrr", "arr", "usd", "fee", "spend", "total"),
    "kw_count": ("count", "cnt", "qty", "quantity", "seats", "users", "signups", "sessions", "num"),
    "kw_pct": ("rate", "pct", "percent", "ratio", "share", "conversion", "churn"),
    "kw_bool": ("is", "has", "active", "flag", "enabled", "verified"),
    "kw_email": ("email", "mail"),
    "kw_url": ("url", "link", "website", "site", "href"),
    "kw_text": ("comment", "note", "description", "feedback", "message", "name", "title"),
}

FEATURE_NAMES: list[str] = [
    "frac_numeric", "frac_int", "frac_date", "frac_currency", "frac_pct", "frac_email",
    "frac_url", "frac_uuid", "frac_bool", "frac_has_space", "unique_ratio", "mean_len",
    "std_len", "mean_words", "frac_0_1", "frac_neg", "is_sequential", "n_values",
    *HEADER_KEYWORDS,
]


def _parse_number(v: str) -> float | None:
    s = v.strip().replace(",", "")
    s = re.sub(r"^[-+]?[$€£₹]\s?", lambda m: "-" if m.group(0).startswith("-") else "", s)
    s = s.rstrip("%").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _is_date(v: str) -> bool:
    s = v.strip()
    if not s or _INT.match(s):
        return False
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(s, fmt)
            return True
        except ValueError:
            continue
    return False


def _header_tokens(header: str) -> set[str]:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", header)
    return {t for t in re.split(r"[^a-z0-9]+", spaced.lower()) if t}


def column_features(example: Example) -> dict[str, float]:
    vals = [v for v in example.values if v is not None and str(v).strip() != ""]
    n = len(vals)
    feats: dict[str, float] = {name: 0.0 for name in FEATURE_NAMES}
    tokens = _header_tokens(example.header)
    for kw, words in HEADER_KEYWORDS.items():
        feats[kw] = float(bool(tokens & set(words)))
    feats["n_values"] = float(n)
    if n == 0:
        return feats

    nums = [_parse_number(v) for v in vals]
    numeric = [x for x in nums if x is not None]
    lens = np.array([len(v) for v in vals], dtype=float)

    def frac(pred) -> float:
        return sum(1 for v in vals if pred(v)) / n

    feats["frac_numeric"] = len(numeric) / n
    feats["frac_int"] = frac(lambda v: bool(_INT.match(v.strip().replace(",", ""))))
    feats["frac_date"] = frac(_is_date)
    feats["frac_currency"] = frac(lambda v: bool(_CURRENCY.search(v)))
    feats["frac_pct"] = frac(lambda v: bool(_PCT.search(v)))
    feats["frac_email"] = frac(lambda v: bool(_EMAIL.match(v.strip())))
    feats["frac_url"] = frac(lambda v: bool(_URL.match(v.strip())))
    feats["frac_uuid"] = frac(lambda v: bool(_UUID.match(v.strip())))
    feats["frac_bool"] = frac(lambda v: v.strip().lower() in _BOOL)
    feats["frac_has_space"] = frac(lambda v: " " in v.strip())
    feats["unique_ratio"] = len(set(vals)) / n
    feats["mean_len"] = float(lens.mean())
    feats["std_len"] = float(lens.std())
    feats["mean_words"] = float(np.mean([len(v.split()) for v in vals]))
    if numeric:
        arr = np.array(numeric)
        feats["frac_0_1"] = float(np.mean((arr >= 0) & (arr <= 1)))
        feats["frac_neg"] = float(np.mean(arr < 0))
        if len(arr) > 2 and feats["frac_int"] == 1.0:
            diffs = np.diff(np.sort(arr))
            feats["is_sequential"] = float(np.mean(diffs == 1) > 0.8)
    return feats


def feature_matrix(examples: list[Example]) -> np.ndarray:
    return np.array([[column_features(e)[k] for k in FEATURE_NAMES] for e in examples])
