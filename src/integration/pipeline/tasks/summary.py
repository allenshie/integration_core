"""Helpers for periodic pipeline summary logs."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any


INGESTION_STATS_RESOURCE = "ingestion_stats"
MC_MOT_STATS_RESOURCE = "mc_mot_stats"
FORMAT_STATS_RESOURCE = "format_stats"
RULE_STATS_RESOURCE = "rule_stats"
EVENT_DISPATCH_STATS_RESOURCE = "event_dispatch_stats"

SUMMARY_INTERVAL_SECONDS = 60.0

SUMMARY_COLUMNS = (
    "raw",
    "events",
    "dropped",
    "tracked",
    "global",
    "signal_groups",
    "warnings",
    "dispatched",
    "skipped",
    "failed",
)

SUMMARY_STAGE_RESOURCES = (
    ("ingestion", INGESTION_STATS_RESOURCE),
    ("mc_mot", MC_MOT_STATS_RESOURCE),
    ("format_conversion", FORMAT_STATS_RESOURCE),
    ("rule_evaluation", RULE_STATS_RESOURCE),
    ("event_dispatch", EVENT_DISPATCH_STATS_RESOURCE),
)


def reset_pipeline_summary(context) -> None:
    for _, resource_key in SUMMARY_STAGE_RESOURCES:
        context.set_resource(resource_key, {})


def store_stage_stats(context, resource_key: str, values: dict[str, Any]) -> None:
    context.set_resource(resource_key, dict(values))


def render_pipeline_summary(context, phase_name: str, window_seconds: float, status: str = "ok") -> str:
    rows = []
    for stage_name, resource_key in SUMMARY_STAGE_RESOURCES:
        stage_stats = context.get_resource(resource_key)
        stage_stats = stage_stats if isinstance(stage_stats, dict) else {}
        row = {"stage": stage_name}
        for column in SUMMARY_COLUMNS:
            row[column] = _format_value(stage_stats.get(column))
        rows.append(row)

    effective_status = "idle" if status == "ok" and _is_idle(rows) else status
    return _render_table(rows, phase_name, window_seconds, effective_status)


def _is_idle(rows: Iterable[dict[str, str]]) -> bool:
    interesting_columns = {"raw", "events", "tracked", "global", "signal_groups", "warnings", "dispatched"}
    for row in rows:
        for column in interesting_columns:
            value = row.get(column, "-")
            if value != "-" and value != "0":
                return False
    return True


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}"
    text = str(value).strip()
    return text if text else "-"


def _render_table(rows: list[dict[str, str]], phase_name: str, window_seconds: float, status: str) -> str:
    header = f"pipeline_summary window={_format_value(window_seconds)}s phase={phase_name or '-'} status={status}"
    columns = ("stage",) + SUMMARY_COLUMNS
    widths: dict[str, int] = {column: len(column) for column in columns}

    for row in rows:
        widths["stage"] = max(widths["stage"], len(row["stage"]))
        for column in SUMMARY_COLUMNS:
            widths[column] = max(widths[column], len(row[column]))

    lines = [header]
    lines.append(_format_row(columns, widths, is_header=True))
    lines.append(_format_separator(columns, widths))
    for row in rows:
        lines.append(_format_row((row["stage"], *[row[column] for column in SUMMARY_COLUMNS]), widths))
    return "\n".join(lines)


def _format_row(values: tuple[str, ...], widths: dict[str, int], is_header: bool = False) -> str:
    stage = values[0]
    columns = values[1:]
    cells = [f"{stage:<{widths['stage']}}"]
    for column_name, value in zip(SUMMARY_COLUMNS, columns):
        if value == "-" or is_header:
            cells.append(f"{value:<{widths[column_name]}}")
        else:
            cells.append(f"{value:>{widths[column_name]}}")
    return " | ".join(cells)


def _format_separator(columns: tuple[str, ...], widths: dict[str, int]) -> str:
    return " | ".join("-" * widths[column] for column in columns)
