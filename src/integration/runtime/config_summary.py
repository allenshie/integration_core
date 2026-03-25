"""Helpers for printing startup configuration summary."""
from __future__ import annotations

import os


def should_print_config_summary() -> bool:
    return os.getenv("CONFIG_SUMMARY", "").strip().lower() in {"1", "true", "yes"}


def log_config_summary(config, context, logger) -> None:
    scheduler = context.get_resource("scheduler")
    scheduler_engine = getattr(scheduler, "_engine", None)
    scheduler_engine_name = scheduler_engine.__class__.__name__ if scheduler_engine else "unknown"
    phase_engine_path = getattr(getattr(config, "phase_task", None), "engine_class", None)
    phase_engine_name = phase_engine_path or "TimeBasedPhaseEngine"
    logger.info(
        "config summary:\n- scheduler_engine: %s\n- phase_engine: %s\n- pipeline_schedule: %s",
        scheduler_engine_name,
        phase_engine_name,
        config.pipeline_schedule_path,
    )
