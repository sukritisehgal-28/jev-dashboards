"""Offline tests for the API predictors: request shape and mapping answers back to keys.

The risky part is renamed/shuffled options: the model answers in presented
names, and the harness must score in canonical keys.
"""

import json
from types import SimpleNamespace

import httpx
import pytest

from jeveval.labels import column_type_options
from jeveval.perturb import STANDARD_VARIANTS, present_options
from jeveval.types import Example

EX = Example(id="t::amount", source="t", header="amount", values=("$12.00", "$7.50"), label="money")


@pytest.fixture
def rotated():
    return present_options(column_type_options(), STANDARD_VARIANTS["rotate"], EX.id)


def test_jev_request_and_mapping(monkeypatch, rotated):
    from jeveval.predictors.jev import JevPredictor

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    seen = {}
    money_name = next(o.name for o in rotated if o.key == "money")

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers["authorization"]
        probs = {o.name: (0.91 if o.key == "money" else 0.01) for o in rotated}
        return httpx.Response(200, json={
            "model": "jev-1.13.0",
            "answers": {"column_type": {"type": "choice", "choice": money_name,
                                        "probabilities": probs, "confidence": 0.91}},
            "usage": {"input_tokens": 1000, "output_tokens": 3},
        })

    jev = JevPredictor()
    jev.http = httpx.Client(transport=httpx.MockTransport(handler), headers=jev.http.headers)
    pred = jev.predict(EX, rotated)

    q = seen["body"]["questions"]["column_type"]
    assert seen["body"]["model"] == "jev-1.13.0"
    assert seen["auth"] == "Bearer test-key"
    assert q["type"] == "choice"
    assert list(q["criteria"]) == [o.name for o in rotated]
    assert pred.label == "money"
    assert pred.cost_usd == pytest.approx(1000 * 0.042 / 1e6)


def test_jev_retries_on_429(monkeypatch, rotated):
    from jeveval.predictors.jev import JevPredictor

    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    monkeypatch.setattr("jeveval.predictors.jev.time.sleep", lambda s: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        probs = {o.name: 1 / len(rotated) for o in rotated}
        return httpx.Response(200, json={"model": "jev-1.13.0", "usage": {},
                                         "answers": {"column_type": {"probabilities": probs}}})

    jev = JevPredictor()
    jev.http = httpx.Client(transport=httpx.MockTransport(handler))
    assert jev.predict(EX, rotated).error is None
    assert calls["n"] == 2


def test_claude_mapping_and_refusal(monkeypatch, rotated):
    from jeveval.predictors.claude import ClaudePredictor

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    claude = ClaudePredictor()
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        answer = {o.name: (0.8 if o.key == "money" else 0.2 / (len(rotated) - 1)) for o in rotated}
        return SimpleNamespace(
            stop_reason="end_turn", model=kwargs["model"], _request_id="req_1",
            usage=SimpleNamespace(input_tokens=500, output_tokens=100),
            content=[SimpleNamespace(type="text", text=json.dumps(answer))],
        )

    monkeypatch.setattr(claude.client.beta.messages, "create", fake_create)
    pred = claude.predict(EX, rotated)
    assert pred.label == "money"
    assert pred.probs["money"] == pytest.approx(0.8)
    assert captured["fallbacks"] == "default"
    schema = captured["output_config"]["format"]["schema"]
    assert set(schema["required"]) == {o.name for o in rotated}

    def refused(**kwargs):
        return SimpleNamespace(stop_reason="refusal", model=kwargs["model"], _request_id="req_2",
                               usage=SimpleNamespace(input_tokens=10, output_tokens=0), content=[])

    monkeypatch.setattr(claude.client.beta.messages, "create", refused)
    assert claude.predict(EX, rotated).error == "refusal"
