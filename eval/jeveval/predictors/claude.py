"""Tier 3: Claude with structured output, asked for a full probability distribution.

Claude's probabilities are verbalized (generated as numbers), not read from
model internals, so their calibration is itself a measurement, not an
assumption.
"""

from __future__ import annotations

import json
import time

import anthropic

from ..types import Example, Option, Prediction
from .base import Predictor, normalize
from .prompting import INSTRUCTIONS, name_to_key, render_criteria, render_state

MODEL = "claude-opus-5-5"
# USD per million tokens, Anthropic first-party pricing as of 2026-10.
INPUT_PER_MTOK = 4.00
OUTPUT_PER_MTOK = 20.00

SYSTEM = (
    "You classify columns of business data tables. Return a probability for every option. "
    "The probabilities must be non-negative and sum to 1, and should reflect how likely you "
    "think each option is correct, so that across many columns your stated probabilities match "
    "how often you are right."
)


class ClaudePredictor(Predictor):
    name = "claude"
    uses_option_text = True

    def __init__(self, model: str = MODEL, effort: str = "medium") -> None:
        self.model = model
        self.effort = effort
        self.client = anthropic.Anthropic()

    def predict(self, example: Example, options: list[Option]) -> Prediction:
        criteria = render_criteria(options)
        schema = {
            "type": "object",
            "properties": {name: {"type": "number"} for name in criteria},
            "required": list(criteria),
            "additionalProperties": False,
        }
        user = (
            f"{INSTRUCTIONS}\n\n"
            f"Options (name: definition):\n{json.dumps(criteria, indent=2)}\n\n"
            f"Column:\n{json.dumps(render_state(example), indent=2)}\n\n"
            "Return a JSON object mapping each option name to its probability."
        )
        start = time.perf_counter()
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=4000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=SYSTEM,
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": schema},
                },
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.RateLimitError as e:
            return self._error(example, f"rate_limited: {e.message}")
        except anthropic.APIStatusError as e:
            return self._error(example, f"api_error {e.status_code}: {e.message}")
        except anthropic.APIConnectionError as e:
            return self._error(example, f"connection_error: {e}")
        latency_ms = (time.perf_counter() - start) * 1000

        usage = response.usage
        cost = (usage.input_tokens * INPUT_PER_MTOK + usage.output_tokens * OUTPUT_PER_MTOK) / 1e6
        base = dict(
            latency_ms=latency_ms,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost,
            meta={"request_id": response._request_id, "served_by": response.model},
        )
        if response.stop_reason == "refusal":
            return Prediction(self.name, "", example.id, {}, error="refusal", **base)
        if response.stop_reason == "max_tokens":
            return Prediction(self.name, "", example.id, {}, error="max_tokens", **base)

        text = next((b.text for b in response.content if b.type == "text"), None)
        try:
            raw = json.loads(text) if text else {}
        except json.JSONDecodeError:
            return Prediction(self.name, "", example.id, {}, error="invalid_json", **base)
        mapping = name_to_key(options)
        by_key = {mapping[n]: float(p) for n, p in raw.items() if n in mapping}
        probs = normalize(by_key, [o.key for o in options])
        return Prediction(self.name, "", example.id, probs, **base)

    def _error(self, example: Example, msg: str) -> Prediction:
        return Prediction(self.name, "", example.id, {}, error=msg)
