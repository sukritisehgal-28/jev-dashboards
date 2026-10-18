"""Perturbations that turn one dataset into several experimental conditions.

Each one targets a documented or hypothesized weakness (PRD hypotheses H2-H4):

- n_values: how many sample values are sent (accuracy vs input-token cost)
- header=drop/swap: does the model trust the header over the values? (H2)
- option_order_seed: first-option bias (H3)
- rename="codes": option names replaced by neutral letters, definitions kept
- rename="rotate": each option shows ANOTHER option's name with its own
  definition, testing whether the name or the definition drives the answer
  (arXiv:2609.26758)
"""

from __future__ import annotations

import hashlib
import random
import string
from dataclasses import replace

from .types import Example, Option, Variant


def _stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(digest[:12], 16)


def present_example(example: Example, variant: Variant, pool: list[Example]) -> Example:
    """Return the example as the predictor will see it under `variant`."""
    values = example.values[: variant.n_values] if variant.n_values > 0 else ()
    header = example.header
    if variant.header == "drop":
        header = ""
    elif variant.header == "swap":
        donors = sorted(
            {e.header for e in pool if e.label != example.label and e.header},
        )
        if donors:
            rng = random.Random(_stable_seed("swap", example.id))
            header = rng.choice(donors)
    elif variant.header != "keep":
        raise ValueError(f"unknown header mode: {variant.header}")
    return replace(example, header=header, values=tuple(values))


def present_options(options: list[Option], variant: Variant, example_id: str) -> list[Option]:
    """Return options in the order and naming the predictor will see."""
    opts = list(options)
    if variant.rename == "codes":
        letters = string.ascii_uppercase
        opts = [replace(o, name=letters[i]) for i, o in enumerate(opts)]
    elif variant.rename == "rotate":
        names = [o.name for o in opts]
        opts = [replace(o, name=names[(i + 1) % len(names)]) for i, o in enumerate(opts)]
    elif variant.rename is not None:
        raise ValueError(f"unknown rename mode: {variant.rename}")
    if variant.option_order_seed is not None:
        rng = random.Random(_stable_seed("order", variant.option_order_seed, example_id))
        rng.shuffle(opts)
    return opts


STANDARD_VARIANTS: dict[str, Variant] = {
    "base": Variant("base"),
    "values0": Variant("values0", n_values=0),
    "values5": Variant("values5", n_values=5),
    "values100": Variant("values100", n_values=100),
    "header_drop": Variant("header_drop", header="drop"),
    "header_swap": Variant("header_swap", header="swap"),
    "shuffle1": Variant("shuffle1", option_order_seed=1),
    "shuffle2": Variant("shuffle2", option_order_seed=2),
    "shuffle3": Variant("shuffle3", option_order_seed=3),
    "codes": Variant("codes", rename="codes"),
    "rotate": Variant("rotate", rename="rotate"),
}
