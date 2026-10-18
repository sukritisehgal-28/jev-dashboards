"""Tier 4: TypeSafe Jev via its documented REST endpoint.

Uses POST https://api.typesafe.ai/v1/systemone (docs.typesafe.ai/api.md)
directly, because the REST reference documents the per-option probabilities
and confidence we need, while the Python SDK usage docs do not.

Terms (typesafe.ai/legal/mca): never train a model on these outputs (2.3(b));
stay under usage limits (2.3(j)). Raw outputs stay in runs/, which is
git-ignored; publish metrics only.
"""

from __future__ import annotations

import os
import threading
import time

import httpx

from ..types import Example, Option, Prediction
from .base import Predictor, normalize
from .prompting import INSTRUCTIONS, name_to_key, render_criteria, render_state

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"  # pinned; jev-latest can change under us
# USD per million input tokens; output is free (docs.typesafe.ai/models, 2026-10).
INPUT_PER_MTOK = 0.042
MAX_ATTEMPTS = 5


class _Throttle:
    """Caps request rate well under the documented 80 requests/second."""

    def __init__(self, per_second: float) -> None:
        self.interval = 1.0 / per_second
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            delay = self.next_at - now
            self.next_at = max(now, self.next_at) + self.interval
        if delay > 0:
            time.sleep(delay)


class JevPredictor(Predictor):
    name = "jev"
    uses_option_text = True

    def __init__(self, model: str = MODEL, requests_per_second: float = 20.0) -> None:
        key = os.environ.get("TYPESAFE_API_KEY")
        if not key:
            raise RuntimeError("Set TYPESAFE_API_KEY (console.typesafe.ai/keys) to run the jev predictor.")
        self.model = model
        self.http = httpx.Client(
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=30.0,
        )
        self.throttle = _Throttle(requests_per_second)

    def predict(self, example: Example, options: list[Option]) -> Prediction:
        body = {
            "model": self.model,
            "state": render_state(example),
            "questions": {
                "column_type": {
                    "type": "choice",
                    "instructions": INSTRUCTIONS,
                    "criteria": render_criteria(options),
                }
            },
        }
        start = time.perf_counter()
        for attempt in range(MAX_ATTEMPTS):
            self.throttle.wait()
            try:
                r = self.http.post(ENDPOINT, json=body)
            except httpx.HTTPError as e:
                if attempt == MAX_ATTEMPTS - 1:
                    return self._error(example, f"connection_error: {e}")
                time.sleep(2**attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                if attempt == MAX_ATTEMPTS - 1:
                    return self._error(example, f"http {r.status_code}")
                time.sleep(float(r.headers.get("retry-after", 2**attempt)))
                continue
            break
        latency_ms = (time.perf_counter() - start) * 1000
        if r.status_code != 200:
            return self._error(example, f"http {r.status_code}: {r.text[:200]}")

        data = r.json()
        answer = data["answers"]["column_type"]
        usage = data.get("usage", {})
        input_tokens = int(usage.get("input_tokens", 0))
        mapping = name_to_key(options)
        by_key = {mapping[n]: float(p) for n, p in answer.get("probabilities", {}).items() if n in mapping}
        return Prediction(
            self.name, "", example.id,
            normalize(by_key, [o.key for o in options]),
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=int(usage.get("output_tokens", 0)),
            cost_usd=input_tokens * INPUT_PER_MTOK / 1e6,
            meta={"served_by": data.get("model"), "jev_confidence": answer.get("confidence")},
        )

    def _error(self, example: Example, msg: str) -> Prediction:
        return Prediction(self.name, "", example.id, {}, error=msg)
