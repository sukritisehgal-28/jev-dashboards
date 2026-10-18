"""Column-type taxonomy for task 1: what kind of data does this column hold?

Definitions are written to be literal and mutually exclusive, because Jev
reads instructions literally (see docs.typesafe.ai/model-jaggedness/jev-1.13).
"""

from __future__ import annotations

from .types import Option

COLUMN_TYPES: dict[str, str] = {
    "id": "An identifier that names one record (user id, order number, UUID). Its numeric value has no meaning.",
    "datetime": "A calendar date, time, or timestamp, in any format.",
    "money": "A monetary amount such as revenue, price, cost, or MRR, with or without a currency symbol.",
    "count": "A whole-number quantity of things (signups, sessions, seats, units).",
    "measure": "A continuous quantity that is not money or a rate (duration, age, width, weight, score).",
    "percentage": "A rate or share, written as 0-100 with or without %, or as a 0-1 fraction.",
    "category": "One of a small set of repeated labels (plan, country, channel, status).",
    "boolean": "A two-valued flag such as true/false, yes/no, or 1/0.",
    "email": "An email address.",
    "url": "A web address or URL.",
    "text": "Free-form human-written text such as comments, descriptions, or names of people.",
}

TASK_INSTRUCTIONS = (
    "You are shown one column from a business data table: its header and a sample of its values. "
    "Decide which kind of data the column holds. Judge mainly by the values; the header may be "
    "abbreviated or wrong."
)


def column_type_options() -> list[Option]:
    return [Option(key=k, name=k, definition=d) for k, d in COLUMN_TYPES.items()]
