"""Core data types shared by datasets, predictors, perturbations and metrics."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Example:
    """One labeled column.

    `source` names the table the column came from. Splits and bootstrap
    resampling are grouped by source so columns of one table never leak
    across folds.
    """

    id: str
    source: str
    header: str
    values: tuple[str, ...]
    label: str
    # Hard-case markers (e.g. "cents_as_int", "misleading_header") for per-slice reporting.
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Option:
    """One answer option shown to a predictor.

    `key` is the canonical label used for scoring. `name` is what the model
    sees; perturbations change `name` (e.g. to neutral codes) and order,
    never `key`.
    """

    key: str
    name: str
    definition: str


@dataclass(frozen=True)
class Variant:
    """How examples and options are presented in one experimental condition."""

    name: str = "base"
    n_values: int = 20  # sample values sent per column; 0 = header only
    header: str = "keep"  # keep | drop | swap (misleading header from another label)
    option_order_seed: int | None = None  # None = canonical order
    rename: str | None = None  # None | "codes" (A, B, C...) | "polarity" (yes/no style names)


@dataclass
class Prediction:
    predictor: str
    variant: str
    example_id: str
    probs: dict[str, float]  # canonical label key -> probability
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: str | None = None
    meta: dict = field(default_factory=dict)

    @property
    def label(self) -> str | None:
        if not self.probs:
            return None
        return max(self.probs, key=self.probs.get)

    @property
    def confidence(self) -> float:
        return max(self.probs.values()) if self.probs else 0.0
