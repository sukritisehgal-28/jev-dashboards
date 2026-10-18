from jeveval.founder_data import INSTANCES, LAYOUTS, MISLEADING, build
from jeveval.labels import COLUMN_TYPES


def test_build_is_deterministic_and_valid():
    a, b = build(), build()
    assert [e.values for e in a] == [e.values for e in b]
    assert len({e.id for e in a}) == len(a)
    assert {e.label for e in a} <= set(COLUMN_TYPES)
    assert all(e.values for e in a)


def test_source_is_the_layout_not_the_instance():
    # Instances of one layout must share a source so grouped CV never splits a template.
    examples = build()
    assert len({e.source for e in examples}) == len(LAYOUTS) + 1
    per_source = {}
    for e in examples:
        per_source.setdefault(e.source, set()).add(e.id.split("::")[2])
    assert all(len(v) == INSTANCES for v in per_source.values())


def test_founder_types_are_well_covered():
    labels = [e.label for e in build()]
    for t in ("money", "percentage", "boolean", "email"):
        assert labels.count(t) >= 15, t


def test_every_misleading_column_is_tagged():
    examples = [e for e in build() if e.source == f"founder:{MISLEADING.name}"]
    assert examples and all("misleading_header" in e.tags for e in examples)
