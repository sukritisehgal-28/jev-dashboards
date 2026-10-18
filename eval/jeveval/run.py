"""Run predictors over a dataset under one or more variants, caching every prediction.

    jeveval --data data/smoke.jsonl --predictors rules,gbm --variants base,header_swap
    jeveval --data data/smoke.jsonl --predictors claude,jev --variants base --limit 10

Re-running with the same --run-dir only fills in missing predictions, so an
interrupted API run resumes where it stopped.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path

from dotenv import load_dotenv
from sklearn.model_selection import GroupKFold

from . import predictors as registry
from .data import load_jsonl
from .labels import column_type_options
from .perturb import STANDARD_VARIANTS, present_example, present_options
from .predictors.base import Predictor
from .report import write_report
from .types import Example, Prediction, Variant

OPTION_ONLY_VARIANTS = {"shuffle1", "shuffle2", "shuffle3", "codes", "rotate"}


def load_cache(path: Path) -> dict[tuple[str, str, str], Prediction]:
    cache: dict[tuple[str, str, str], Prediction] = {}
    if path.exists():
        with open(path) as f:
            for line in f:
                p = Prediction(**json.loads(line))
                if p.error is None:
                    cache[(p.predictor, p.variant, p.example_id)] = p
    return cache


def _predict_one(predictor: Predictor, example: Example, variant: Variant, pool: list[Example]) -> Prediction:
    shown = present_example(example, variant, pool)
    options = present_options(column_type_options(), variant, example.id)
    pred = predictor.predict(shown, options)
    return replace(pred, predictor=predictor.name, variant=variant.name, example_id=example.id)


def run_trainable(predictor: Predictor, examples: list[Example], variant: Variant, folds: int) -> list[Prediction]:
    """Out-of-fold predictions with folds grouped by source table (no within-table leakage)."""
    groups = [e.source for e in examples]
    n_splits = min(folds, len(set(groups)))
    out = []
    for train_idx, test_idx in GroupKFold(n_splits=n_splits).split(examples, groups=groups):
        train = [present_example(examples[i], variant, examples) for i in train_idx]
        train = [replace(t, label=examples[i].label) for t, i in zip(train, train_idx)]
        predictor.fit(train)
        out.extend(_predict_one(predictor, examples[i], variant, examples) for i in test_idx)
    return out


def run(args: argparse.Namespace) -> Path:
    load_dotenv()
    examples = load_jsonl(args.data)
    if args.limit:
        examples = examples[: args.limit]
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    pred_path = run_dir / "predictions.jsonl"
    cache = load_cache(pred_path)

    variants = [STANDARD_VARIANTS[v] for v in args.variants.split(",")]
    for name in args.predictors.split(","):
        kwargs = {"effort": args.claude_effort} if name == "claude" else {}
        predictor = registry.build(name, **kwargs)
        for variant in variants:
            if not predictor.uses_option_text and variant.name in OPTION_ONLY_VARIANTS:
                print(f"skip {name}/{variant.name}: predictor ignores option names and order")
                continue
            todo = [e for e in examples if (name, variant.name, e.id) not in cache]
            if not todo:
                print(f"{name}/{variant.name}: cached")
                continue
            print(f"{name}/{variant.name}: predicting {len(todo)} columns")
            if predictor.trainable:
                # Out-of-fold needs the whole dataset; recompute every fold.
                preds = run_trainable(predictor, examples, variant, args.folds)
            else:
                with ThreadPoolExecutor(max_workers=args.workers) as pool:
                    preds = list(pool.map(lambda e: _predict_one(predictor, e, variant, examples), todo))
            errors = [p for p in preds if p.error]
            with open(pred_path, "a") as f:
                for p in preds:
                    f.write(json.dumps(asdict(p)) + "\n")
                    if p.error is None:
                        cache[(p.predictor, p.variant, p.example_id)] = p
            if errors:
                print(f"  {len(errors)} errors, e.g. {errors[0].error}; re-run to retry them", file=sys.stderr)

    write_report(examples, list(cache.values()), run_dir, cost_error=args.cost_error, cost_defer=args.cost_defer)
    return run_dir


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="labeled columns JSONL")
    ap.add_argument("--predictors", default="rules,gbm", help=f"comma list from {registry.ALL}")
    ap.add_argument("--variants", default="base", help=f"comma list from {sorted(STANDARD_VARIANTS)}")
    ap.add_argument("--run-dir", default="runs/latest")
    ap.add_argument("--limit", type=int, default=0, help="only the first N columns (cheap API trial)")
    ap.add_argument("--workers", type=int, default=4, help="parallel API requests")
    ap.add_argument("--folds", type=int, default=5, help="grouped CV folds for trainable predictors")
    ap.add_argument("--claude-effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--cost-error", type=float, default=1.0, help="cost of one wrong automatic decision")
    ap.add_argument("--cost-defer", type=float, default=0.1, help="cost of sending one decision to a person")
    run_dir = run(ap.parse_args(argv))
    print(f"report: {run_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
