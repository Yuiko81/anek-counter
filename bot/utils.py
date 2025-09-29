from __future__ import annotations

from typing import Any, Iterable


def parse_period(period: str | None) -> str:
    if period is None:
        return "week"
    period = period.lower()
    if period not in {"day", "week", "month", "all"}:
        raise ValueError("Unknown period")
    return period


def build_personal_summary(records: Iterable[Any]) -> dict[str, dict[str, int | float]]:
    summary: dict[str, dict[str, int | float]] = {}
    for record in records:
        summary[record["code"]] = {
            "count": record["total_events"],
            "minutes": record["total_minutes"],
            "rating": float(record.get("avg_rating", 0) or 0),
        }
    return summary

