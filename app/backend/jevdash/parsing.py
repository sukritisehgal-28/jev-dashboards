"""Turning strings into typed values. Pure code: Jev never does arithmetic or date logic."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

TRUE_WORDS = {"true", "yes", "y", "1", "✓", "✔", "t", "x"}


def parse_datetime(s: pd.Series) -> pd.Series:
    """Unix seconds/millis, YYYYMMDD, dd.mm.yyyy and anything pandas can read. Returns UTC timestamps."""
    v = s.astype(str).str.strip()
    present = v[v != ""]
    if len(present) and present.str.fullmatch(r"\d+").all():
        n = present.str.len().mode()[0]
        if n == 10:
            return pd.to_datetime(pd.to_numeric(v, errors="coerce"), unit="s", utc=True)
        if n == 13:
            return pd.to_datetime(pd.to_numeric(v, errors="coerce"), unit="ms", utc=True)
        if n == 8:
            return pd.to_datetime(v, format="%Y%m%d", errors="coerce", utc=True)
    dayfirst = bool(present.str.contains(r"^\d{1,2}\.\d{1,2}\.\d{4}").any())
    return pd.to_datetime(v, format="mixed", dayfirst=dayfirst, errors="coerce", utc=True)


def _number(x: str) -> float:
    x = x.strip()
    if not x:
        return np.nan
    neg = (x.startswith("(") and x.endswith(")")) or x.lstrip("$€£₹ ").startswith("-") or x.startswith("-")
    x = re.sub(r"[^\d,.]", "", x)
    # European decimals: "1.234,56" or "296,55". A comma followed by exactly three digits
    # ("45,000") is a thousands separator, the far more common case in exports.
    if re.fullmatch(r"\d{1,3}(\.\d{3})+,\d+|\d+,\d{1,2}", x):
        x = x.replace(".", "").replace(",", ".")
    x = x.replace(",", "")
    try:
        return -float(x) if neg else float(x)
    except ValueError:
        return np.nan


def parse_number(s: pd.Series) -> pd.Series:
    """$1,234.56, 1.234,56 €, (1,140.00), -45,000, 12.5% and plain numbers."""
    return s.astype(str).map(_number).astype(float)


def parse_bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().isin(TRUE_WORDS)
