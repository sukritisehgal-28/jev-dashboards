"""Baseline tiers: rules -> classic ML -> Claude -> Jev."""

from __future__ import annotations

from .base import Predictor


def build(name: str, **kwargs) -> Predictor:
    """Construct a predictor by name. API clients are imported lazily."""
    if name == "rules":
        from .rules import RulesPredictor
        return RulesPredictor()
    if name == "gbm":
        from .gbm import GBMPredictor
        return GBMPredictor()
    if name == "claude":
        from .claude import ClaudePredictor
        return ClaudePredictor(**kwargs)
    if name == "jev":
        from .jev import JevPredictor
        return JevPredictor(**kwargs)
    raise ValueError(f"unknown predictor: {name}")


ALL = ("rules", "gbm", "claude", "jev")
