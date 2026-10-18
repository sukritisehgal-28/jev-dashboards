"""Tier 1: hand-written rules over value statistics, with the header as a tie-breaker.

The floor every model has to beat. If a model cannot beat this, its cost is
not justified for that column type.
"""

from __future__ import annotations

from ..features import column_features
from ..types import Example, Option, Prediction
from .base import Predictor, normalize

_CONFIDENT = 0.85
_LEANING = 0.6


class RulesPredictor(Predictor):
    name = "rules"

    def predict(self, example: Example, options: list[Option]) -> Prediction:
        keys = [o.key for o in options]
        label, strength = self._decide(column_features(example))
        rest = (1.0 - strength) / (len(keys) - 1)
        probs = {k: (strength if k == label else rest) for k in keys}
        return Prediction(self.name, "", example.id, normalize(probs, keys))

    @staticmethod
    def _decide(f: dict[str, float]) -> tuple[str, float]:
        if f["n_values"] == 0:
            for kw, label in (
                ("kw_email", "email"), ("kw_url", "url"), ("kw_date", "datetime"),
                ("kw_pct", "percentage"), ("kw_money", "money"), ("kw_bool", "boolean"),
                ("kw_id", "id"), ("kw_count", "count"), ("kw_text", "text"),
            ):
                if f[kw]:
                    return label, _LEANING
            return "category", 0.2
        if f["frac_email"] > 0.8:
            return "email", _CONFIDENT
        if f["frac_url"] > 0.8:
            return "url", _CONFIDENT
        if f["frac_uuid"] > 0.8:
            return "id", _CONFIDENT
        if f["frac_date"] > 0.8:
            return "datetime", _CONFIDENT
        if f["frac_bool"] > 0.95 and f["unique_ratio"] <= 0.5:
            return "boolean", _CONFIDENT
        if f["frac_pct"] > 0.8:
            return "percentage", _CONFIDENT
        if f["frac_currency"] > 0.8:
            return "money", _CONFIDENT
        if f["frac_numeric"] > 0.9:
            if f["kw_id"] or (f["is_sequential"] and f["unique_ratio"] == 1.0):
                return "id", _LEANING
            if f["kw_pct"] or (f["frac_0_1"] == 1.0 and f["frac_int"] < 1.0):
                return "percentage", _LEANING
            if f["kw_money"]:
                return "money", _LEANING
            if f["frac_int"] < 0.5:
                return "measure", _LEANING
            return "count", _LEANING
        if f["unique_ratio"] < 0.5 and f["mean_words"] <= 3:
            return "category", _LEANING
        if f["mean_words"] > 3:
            return "text", _LEANING
        if f["unique_ratio"] == 1.0 and f["frac_has_space"] < 0.2:
            return "id", _LEANING
        return "text", 0.3
