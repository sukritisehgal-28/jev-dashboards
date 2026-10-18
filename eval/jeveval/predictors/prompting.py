"""One shared rendering of the task, so Claude and Jev see identical inputs."""

from __future__ import annotations

from ..labels import TASK_INSTRUCTIONS
from ..types import Example, Option


def render_state(example: Example) -> dict:
    return {
        "column_header": example.header or "(no header)",
        "sample_values": list(example.values),
    }


def render_criteria(options: list[Option]) -> dict[str, str]:
    """Option name -> definition, in presented order."""
    return {o.name: o.definition for o in options}


def name_to_key(options: list[Option]) -> dict[str, str]:
    return {o.name: o.key for o in options}


INSTRUCTIONS = TASK_INSTRUCTIONS
