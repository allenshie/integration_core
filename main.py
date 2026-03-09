"""Entry point for the integration daemon."""
from __future__ import annotations

import logging
import os
import sys
from contextlib import suppress
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
SRC_DIR = CURRENT_DIR / "src"

if __package__ in {None, ""}:  # support running via `python main.py`
    for path in (PARENT_DIR, SRC_DIR):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

from dotenv import load_dotenv

# 先載入 repo 根目錄/.env（若有），再載入 integration/.env 覆寫
load_dotenv(PARENT_DIR / ".env")
load_dotenv(CURRENT_DIR / ".env", override=True)

from integration.utils.paths import set_core_root

set_core_root(CURRENT_DIR)

from integration.config.settings import AppConfig, load_config
from integration.api.event_store import EdgeEventStore
from integration.comm import build_edge_comm_adapter
from integration.pipeline.pipeline import InitPipelineTask
from integration.pipeline.control.scheduler import PipelineScheduler
from integration.pipeline.control import PhaseTask
from smart_workflow import (
    HealthAwareWorkflowRunner,
    HealthServer,
    HealthState,
    MonitoringClient,
    ProbeConfig,
    TaskContext,
    Workflow,
    WorkflowRunner,
)

LOGGER = logging.getLogger(__name__)

def setup_logging(level: str = "INFO") -> None:
    level_value = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=level_value,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def build_context(config: AppConfig) -> TaskContext:
    monitor = MonitoringClient(
        config.monitor_endpoint,
        service_name=config.monitor_service_name,
    )
    context = TaskContext(logger=LOGGER, config=config, monitor=monitor)
    scheduler_cfg = getattr(config, "scheduler", None)
    engine_class = getattr(scheduler_cfg, "engine_class", None) if scheduler_cfg else None
    context.set_resource(
        "scheduler",
        PipelineScheduler(config.working_windows, config.timezone, engine_class, context=context),
    )
    context.set_resource("edge_event_store", EdgeEventStore())
    return context



def build_workflow() -> Workflow:
    workflow = Workflow()
    workflow.add_startup_task(lambda: InitPipelineTask())
    workflow.set_loop(lambda: PhaseTask())
    return workflow


def run_daemon(config: AppConfig) -> None:
    context = build_context(config)
    if os.getenv("CONFIG_SUMMARY", "").strip().lower() in {"1", "true", "yes"}:
        scheduler = context.get_resource("scheduler")
        scheduler_engine = getattr(scheduler, "_engine", None)
        scheduler_engine_name = scheduler_engine.__class__.__name__ if scheduler_engine else "unknown"
        phase_engine_path = getattr(getattr(config, "phase_task", None), "engine_class", None)
        phase_engine_name = phase_engine_path or "TimeBasedPhaseEngine"
        LOGGER.info(
            "config summary:\n- scheduler_engine: %s\n- phase_engine: %s\n- pipeline_schedule: %s",
            scheduler_engine_name,
            phase_engine_name,
            config.pipeline_schedule_path,
        )
    store = context.require_resource("edge_event_store")
    _start_edge_event_receiver(config, context, store)
    workflow = build_workflow()
    health_server: HealthServer | None = None
    health_state: HealthState | None = None
    health_enabled = _to_bool(os.getenv("INTEGRATION_HEALTH_SERVER_ENABLED"), False)
    print()
    if health_enabled:
        health_state = HealthState()
        context.set_resource("health_state", health_state)
        health_server = HealthServer(
            health_state=health_state,
            host=os.environ.get("INTEGRATION_HEALTH_SERVER_HOST", "0.0.0.0"),
            port=int(os.environ.get("INTEGRATION_HEALTH_SERVER_PORT", "8081")),
            probe_config=ProbeConfig(
                liveness_timeout_seconds=float(
                    os.environ.get("INTEGRATION_HEALTH_LIVENESS_TIMEOUT_SECONDS", "30")
                ),
                readiness_timeout_seconds=float(
                    os.environ.get("INTEGRATION_HEALTH_READINESS_TIMEOUT_SECONDS", "30")
                ),
                startup_grace_seconds=float(
                    os.environ.get("INTEGRATION_HEALTH_STARTUP_GRACE_SECONDS", "10")
                ),
            ),
        )
        health_server.start()
        LOGGER.info(
            "health server started at %s:%s",
            os.environ.get("INTEGRATION_HEALTH_SERVER_HOST", "0.0.0.0"),
            os.environ.get("INTEGRATION_HEALTH_SERVER_PORT", "8081"),
        )
    if health_state is not None:
        runner = HealthAwareWorkflowRunner(
            context=context,
            workflow=workflow,
            loop_interval=config.loop_interval_seconds,
            retry_backoff=config.retry_backoff_seconds,
            health_state=health_state,
        )
    else:
        runner = WorkflowRunner(
            context=context,
            workflow=workflow,
            loop_interval=config.loop_interval_seconds,
            retry_backoff=config.retry_backoff_seconds,
        )

    try:
        runner.run()
    finally:
        if health_server is not None:
            health_server.stop()


def _start_edge_event_receiver(config: AppConfig, context: TaskContext, store: EdgeEventStore) -> None:
    adapter = build_edge_comm_adapter(config, logger=LOGGER)
    context.set_resource("edge_comm_adapter", adapter)
    try:
        adapter.start_event_ingestion(store.add_event)
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.warning("edge event ingestion start failed: %s", exc)
    LOGGER.info(
        "edge comm adapter ready (ingestion=%s, phase_publish=%s)",
        config.edge_event_backend,
        getattr(config.phase_publish, "backend", config.edge_event_backend),
    )


def main() -> int:
    config = load_config()
    setup_logging(config.log_level)
    run_daemon(config)
    return 0


if __name__ == "__main__":
    with suppress(SystemExit):
        sys.exit(main())
