from jeveval.labels import column_type_options
from jeveval.perturb import STANDARD_VARIANTS, present_example, present_options
from jeveval.predictors.rules import RulesPredictor
from jeveval.types import Example, Variant


def _ex(header, values, label, source="t"):
    return Example(id=f"{source}::{header}", source=source, header=header, values=tuple(values), label=label)


def test_rename_and_shuffle_keep_keys_and_definitions():
    opts = column_type_options()
    for name in ("codes", "rotate", "shuffle1"):
        shown = present_options(opts, STANDARD_VARIANTS[name], "x")
        assert sorted(o.key for o in shown) == sorted(o.key for o in opts)
        defs = {o.key: o.definition for o in opts}
        assert all(o.definition == defs[o.key] for o in shown)


def test_rotate_gives_every_option_a_wrong_name():
    shown = present_options(column_type_options(), STANDARD_VARIANTS["rotate"], "x")
    assert all(o.name != o.key for o in shown)


def test_shuffle_is_deterministic_per_example():
    opts = column_type_options()
    v = STANDARD_VARIANTS["shuffle1"]
    assert present_options(opts, v, "a") == present_options(opts, v, "a")


def test_header_swap_uses_header_of_a_different_label():
    pool = [_ex("email", ["a@b.co"], "email"), _ex("signups", ["4"], "count"), _ex("amount", ["$3"], "money")]
    shown = present_example(pool[0], Variant("s", header="swap"), pool)
    assert shown.header in {"signups", "amount"}
    assert shown.values == pool[0].values


def test_values_zero_sends_header_only():
    e = _ex("mrr", ["1", "2"], "money")
    assert present_example(e, STANDARD_VARIANTS["values0"], [e]).values == ()


def test_rules_handle_clear_cases():
    rules = RulesPredictor()
    opts = column_type_options()
    cases = [
        _ex("x", ["ana@acme.io", "li@x.com", "mo@y.org"], "email"),
        _ex("x", ["https://a.com", "https://b.io/p", "www.c.co"], "url"),
        _ex("x", ["2026-01-02", "2026-03-04", "2025-12-31"], "datetime"),
        _ex("x", ["4.5%", "12%", "0.8%"], "percentage"),
        _ex("x", ["$12.00", "$7.50", "$99.00"], "money"),
        _ex("x", ["yes", "no", "yes", "no", "no", "yes"], "boolean"),
    ]
    for e in cases:
        assert rules.predict(e, opts).label == e.label, e
