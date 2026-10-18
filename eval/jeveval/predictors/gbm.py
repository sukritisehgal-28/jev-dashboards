"""Tier 2: gradient-boosted classifier on Sherlock-style features.

A trained classic model: cheap, fast, local. It shows how much of the task is
solvable without any LLM once you have labels.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from ..features import feature_matrix
from ..types import Example, Option, Prediction
from .base import Predictor, normalize


class GBMPredictor(Predictor):
    name = "gbm"
    trainable = True

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed
        self.model: HistGradientBoostingClassifier | None = None
        self.classes_: list[str] = []

    def fit(self, examples: list[Example]) -> None:
        X = feature_matrix(examples)
        y = np.array([e.label for e in examples])
        self.model = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.1, min_samples_leaf=2, random_state=self.seed
        )
        self.model.fit(X, y)
        self.classes_ = list(self.model.classes_)

    def predict(self, example: Example, options: list[Option]) -> Prediction:
        if self.model is None:
            raise RuntimeError("GBMPredictor.predict called before fit")
        keys = [o.key for o in options]
        proba = self.model.predict_proba(feature_matrix([example]))[0]
        probs = dict(zip(self.classes_, proba))
        # Classes absent from the training fold get a small floor so log loss stays finite.
        floored = {k: probs.get(k, 0.0) + 1e-3 for k in keys}
        return Prediction(self.name, "", example.id, normalize(floored, keys))
