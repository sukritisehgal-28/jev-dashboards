"""Backend tests. JEV_MOCK=1 everywhere: no network, no credits."""

import json

import pandas as pd
import pytest

from jevdash import sources
from jevdash.parsing import parse_bool, parse_datetime, parse_number
from jevdash.spec import build_spec, cents_decision


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_MOCK", "1")
    monkeypatch.setenv("JEVDASH_STORAGE", str(tmp_path))
    from fastapi.testclient import TestClient

    from jevdash import api

    for f in (api.store, api.ledger, api.jev):
        f.cache_clear()
    return TestClient(api.app)


def test_parse_number_formats():
    s = pd.Series(["$1,234.56", "1.234,56 €", "($1,140.00)", "-45,000", "12.5%", "", "abc"])
    out = parse_number(s).tolist()
    assert out[:5] == [1234.56, 1234.56, -1140.0, -45000.0, 12.5]
    assert pd.isna(out[5]) and pd.isna(out[6])


def test_parse_datetime_formats():
    assert parse_datetime(pd.Series(["1746824420"])).iloc[0].year == 2025
    assert parse_datetime(pd.Series(["1747147352000"])).iloc[0].year == 2025
    assert parse_datetime(pd.Series(["20250101"])).iloc[0].month == 1
    assert parse_datetime(pd.Series(["12.07.2026"])).iloc[0].month == 7  # day first


def test_parse_bool():
    assert parse_bool(pd.Series(["✓", "", "TRUE", "no", "Yes"])).tolist() == [True, False, True, False, True]


def test_cents_decision_statuses():
    assert cents_decision("a", {"cents": 0.44, "cents_table": 0.93}, {})["status"] == "decided"
    unsure = cents_decision("a", {"cents": 0.44, "cents_table": 0.55}, {})
    assert unsure["status"] == "needs_confirmation" and unsure["divide"] is True
    assert cents_decision("a", {"cents": 0.9}, {"a": False}) == {
        "column": "a", "divide": False, "status": "confirmed", "p_column": 0.9, "p_table": None}


def _decision(t, role, cents=0.05, filt=0.05):
    return {"type": t, "type_p": {t: 0.99}, "role": role, "cents": cents, "cents_table": cents, "filter": filt}


def test_spec_filters_divides_and_charts():
    df = pd.DataFrame({
        "created": ["1735689600", "1738368000", "1740787200", "1740787200"],  # Jan, Feb, Mar(x2) 2025
        "amount": ["2900", "9900", "2900", "5000"],
        "paid": ["true", "true", "false", "true"],
        "plan": ["A", "B", "A", "B"],
    })
    decisions = {"created": _decision("datetime", "time"), "amount": _decision("money", "sum", cents=0.95),
                 "paid": _decision("boolean", "group_by", filt=0.9), "plan": _decision("category", "group_by")}
    spec = build_spec(df, decisions, {})
    total = next(k for k in spec["kpis"] if k["label"] == "Total amount")
    assert total["value"] == 29 + 99 + 50  # cents divided, unpaid row excluded
    by_month = next(c for c in spec["charts"] if c["id"] == "amount-by-month")
    assert [p["x"] for p in by_month["points"]] == ["2025-01", "2025-02"]  # partial latest month dropped
    by_plan = next(c for c in spec["charts"] if c["id"] == "amount-by-plan")
    assert {p["x"]: p["y"] for p in by_plan["points"]} == {"B": 149.0, "A": 29.0}


def test_sheets_url_normalization():
    url = "https://docs.google.com/spreadsheets/d/abc_123-XYZ/edit#gid=42"
    assert sources.sheets_csv_url(url) == "https://docs.google.com/spreadsheets/d/abc_123-XYZ/export?format=csv&gid=42"
    for bad in ("http://docs.google.com/spreadsheets/d/x", "https://evil.com/spreadsheets/d/x", "https://docs.google.com/forms/d/x"):
        with pytest.raises(sources.SourceError):
            sources.sheets_csv_url(bad)


def test_json_upload_shapes():
    assert len(sources.read_json_bytes(json.dumps([{"a": 1}, {"a": 2}]).encode())) == 2
    assert list(sources.read_json_bytes(json.dumps({"data": [{"a": {"b": 1}}]}).encode()).columns) == ["a.b"]
    with pytest.raises(sources.SourceError):
        sources.read_json_bytes(b'{"x": 1}')


def test_api_sample_upload_confirm_delete(client):
    r = client.post("/api/datasets/sample")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dataset"]["rows"] > 1000
    assert body["jev"]["source"].startswith("mock")
    assert body["spec"]["kpis"] and body["spec"]["charts"]
    ds = body["dataset"]["id"]

    assert client.get(f"/api/datasets/{ds}").json()["dataset"]["id"] == ds
    assert client.get("/api/datasets").json()[0]["id"] == ds

    r = client.post(f"/api/datasets/{ds}/confirm", json={"column": "amount", "cents": True})
    unit = next(u for u in r.json()["spec"]["units"] if u["column"] == "amount")
    assert unit == {**unit, "divide": True, "status": "confirmed"}

    csv = b"day,signups\n2025-01-01,4\n2025-01-02,7\n"
    up = client.post("/api/datasets/upload", files={"file": ("kpis.csv", csv, "text/csv")})
    assert up.status_code == 200 and up.json()["dataset"]["name"] == "kpis"

    assert client.delete(f"/api/datasets/{ds}").status_code == 200
    assert client.get(f"/api/datasets/{ds}").status_code == 404


def test_api_rejects_bad_input(client):
    assert client.post("/api/datasets/upload", files={"file": ("x.json", b"not json", "application/json")}).status_code == 400
    assert client.post("/api/datasets/sheets", json={"url": "https://example.com/x"}).status_code == 400
    assert client.get("/api/datasets/../etc").status_code == 404
