"""Common interface for every baseline tier."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import Example, Option, Prediction


class Predictor(ABC):
    """Maps a presented column plus presented options to a distribution over option keys.

    Zero-shot predictors (rules, Claude, Jev) ignore `fit`. Trainable ones are
    fit on other folds by the runner (grouped cross-validation), never on the
    example they predict.
    """

    name: str = "base"
    trainable: bool = False
    # Predictors whose output cannot depend on option names/order skip those variants.
    uses_option_text: bool = False

    def fit(self, examples: list[Example]) -> None:  # noqa: B027 - optional hook
        pass

    @abstractmethod
    def predict(self, example: Example, options: list[Option]) -> Prediction:
        """Return a Prediction with `probs` keyed by Option.key (canonical labels)."""


def normalize(probs: dict[str, float], keys: list[str]) -> dict[str, float]:
    """Restrict to `keys`, clip negatives, renormalize; uniform if everything is zero."""
    clean = {k: max(float(probs.get(k, 0.0)), 0.0) for k in keys}
    total = sum(clean.values())
    if total <= 0:
        return {k: 1.0 / len(keys) for k in keys}
    return {k: v / total for k, v in clean.items()}
