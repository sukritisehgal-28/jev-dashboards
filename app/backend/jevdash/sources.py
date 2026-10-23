"""Getting a table in: file upload (CSV or JSON) or a Google Sheets link.

Everything is read as strings; typing is Jev's job and parsing is code's.
"""

from __future__ import annotations

import io
import json
import re
from urllib.parse import parse_qs, urlparse

import httpx
import pandas as pd

MAX_BYTES = 20 * 1024 * 1024
MAX_ROWS = 200_000
MAX_COLUMNS = 60  # also bounds Jev calls per dataset


class SourceError(ValueError):
    pass


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df.columns) == 0:
        raise SourceError("The table is empty.")
    if len(df.columns) > MAX_COLUMNS:
        raise SourceError(f"Too many columns ({len(df.columns)}); the limit is {MAX_COLUMNS}.")
    df = df.head(MAX_ROWS).copy()
    df.columns = [str(c).strip() or f"column_{i + 1}" for i, c in enumerate(df.columns)]
    if len(set(df.columns)) != len(df.columns):
        raise SourceError("Column names must be unique.")
    return df.fillna("").astype(str)


def read_csv_bytes(content: bytes) -> pd.DataFrame:
    try:
        return _finish(pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False, encoding_errors="replace"))
    except pd.errors.ParserError as e:
        raise SourceError(f"Could not parse CSV: {e}") from e


def read_json_bytes(content: bytes) -> pd.DataFrame:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise SourceError(f"Invalid JSON: {e}") from e
    if isinstance(data, dict):  # {"data": [...]} or {"rows": [...]} style wrappers
        lists = [v for v in data.values() if isinstance(v, list)]
        if len(lists) != 1:
            raise SourceError("JSON must be an array of objects, or an object holding exactly one such array.")
        data = lists[0]
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        raise SourceError("JSON must be an array of objects.")
    return _finish(pd.json_normalize(data))


def read_upload(filename: str, content: bytes) -> pd.DataFrame:
    if len(content) > MAX_BYTES:
        raise SourceError("File is larger than 20 MB.")
    if filename.lower().endswith(".json"):
        return read_json_bytes(content)
    return read_csv_bytes(content)


_SHEET_ID = re.compile(r"^/spreadsheets/d/([A-Za-z0-9_-]+)")


def sheets_csv_url(url: str) -> str:
    """Normalize a Google Sheets link to its CSV export URL. Only docs.google.com links are accepted."""
    u = urlparse(url.strip())
    if u.scheme != "https" or u.hostname != "docs.google.com":
        raise SourceError("Paste a https://docs.google.com/spreadsheets/... link.")
    m = _SHEET_ID.match(u.path)
    if not m:
        raise SourceError("That doesn't look like a Google Sheets link.")
    gid = parse_qs(u.query).get("gid", [None])[0] or parse_qs(u.fragment).get("gid", [None])[0] or "0"
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv&gid={gid}"


def fetch_sheet(url: str) -> pd.DataFrame:
    export = sheets_csv_url(url)
    try:
        r = httpx.get(export, follow_redirects=True, timeout=20)
    except httpx.HTTPError as e:
        raise SourceError(f"Could not reach Google Sheets: {e}") from e
    if r.status_code != 200 or "text/csv" not in r.headers.get("content-type", ""):
        raise SourceError("Could not read the sheet. Share it as 'Anyone with the link can view' and try again.")
    if len(r.content) > MAX_BYTES:
        raise SourceError("Sheet is larger than 20 MB.")
    return read_csv_bytes(r.content)
