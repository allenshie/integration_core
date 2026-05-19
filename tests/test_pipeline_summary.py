from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SMART_WORKFLOW_ROOT = Path(__file__).resolve().parents[3] / "test_space" / "smart-workflow"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SMART_WORKFLOW_ROOT) not in sys.path:
    sys.path.insert(0, str(SMART_WORKFLOW_ROOT))

for module_name in list(sys.modules):
    if module_name == "integration" or module_name.startswith("integration."):
        sys.modules.pop(module_name)

from smart_workflow import TaskResult

from integration.pipeline.tasks.base import QuietTaskBase
from integration.pipeline.tasks.pipelines.mcmot_pipeline import MCMOTPipelineTask
from integration.pipeline.tasks.summary import (
    EVENT_DISPATCH_STATS_RESOURCE,
    FORMAT_STATS_RESOURCE,
    INGESTION_STATS_RESOURCE,
    MC_MOT_STATS_RESOURCE,
    RULE_STATS_RESOURCE,
    render_pipeline_summary,
    reset_pipeline_summary,
    store_stage_stats,
)


class DummyContext:
    def __init__(self, resources: dict[str, object] | None = None) -> None:
        self._resources = dict(resources or {})
        self.logger = logging.getLogger("pipeline-summary-test")
        self.config = SimpleNamespace(pipeline_summary_interval_seconds=60.0)
        self.reported_success: list[str] = []
        self.reported_failure: list[tuple[str, str | None]] = []

    def get_resource(self, key: str):
        return self._resources.get(key)

    def set_resource(self, key: str, value) -> None:  # noqa: ANN001
        self._resources[key] = value

    def report_success(self, name: str) -> None:
        self.reported_success.append(name)

    def report_failure(self, name: str, detail: str | None = None) -> None:
        self.reported_failure.append((name, detail))


class DummyTask(QuietTaskBase):
    name = "dummy_task"

    def run(self, context: DummyContext) -> TaskResult:
        _ = context
        return TaskResult(status="done")


class DummyNode:
    def __init__(self, resource_key: str, values: dict[str, int]) -> None:
        self._resource_key = resource_key
        self._values = values

    def execute(self, context: DummyContext) -> None:
        store_stage_stats(context, self._resource_key, self._values)


def build_context() -> DummyContext:
    return DummyContext(
        {
            "phase_task_state": {"last_phase": "working"},
        }
    )


def test_render_pipeline_summary_outputs_table() -> None:
    context = build_context()
    reset_pipeline_summary(context)
    store_stage_stats(
        context,
        INGESTION_STATS_RESOURCE,
        {"raw": 18, "events": 3, "dropped": 1},
    )
    store_stage_stats(
        context,
        MC_MOT_STATS_RESOURCE,
        {"events": 3, "tracked": 7, "global": 4},
    )
    store_stage_stats(
        context,
        FORMAT_STATS_RESOURCE,
        {"events": 3, "tracked": 7, "global": 4, "signal_groups": 2},
    )
    store_stage_stats(
        context,
        RULE_STATS_RESOURCE,
        {"warnings": 5},
    )
    store_stage_stats(
        context,
        EVENT_DISPATCH_STATS_RESOURCE,
        {"dispatched": 5, "skipped": 0, "failed": 0},
    )

    summary = render_pipeline_summary(context, "working", 60.0)
    summary_lines = summary.splitlines()

    assert "pipeline_summary window=60s phase=working status=ok" in summary
    assert any(line.startswith("stage") and "| raw" in line for line in summary_lines)
    assert any(line.startswith("ingestion") for line in summary_lines)
    assert any(line.startswith("mc_mot") for line in summary_lines)
    assert any(line.startswith("format_conversion") for line in summary_lines)
    assert any(line.startswith("rule_evaluation") for line in summary_lines)
    assert any(line.startswith("event_dispatch") for line in summary_lines)


def test_quiet_task_base_execute_suppresses_start_log(caplog) -> None:
    context = build_context()
    context.logger.setLevel(logging.DEBUG)
    task = DummyTask()

    with caplog.at_level(logging.INFO, logger="pipeline-summary-test"):
        result = task.execute(context)

    assert result.status == "done"
    assert "開始任務：dummy_task" not in caplog.text
    assert context.reported_success == ["dummy_task"]


def test_pipeline_summary_logs_once_per_interval(caplog, monkeypatch) -> None:
    context = build_context()
    context.logger.setLevel(logging.INFO)
    pipeline = MCMOTPipelineTask(
        context,
        nodes=[
            DummyNode(INGESTION_STATS_RESOURCE, {"raw": 12, "events": 4, "dropped": 0}),
            DummyNode(MC_MOT_STATS_RESOURCE, {"events": 4, "tracked": 8, "global": 2}),
            DummyNode(FORMAT_STATS_RESOURCE, {"events": 4, "tracked": 8, "global": 2, "signal_groups": 1}),
            DummyNode(RULE_STATS_RESOURCE, {"warnings": 3}),
            DummyNode(EVENT_DISPATCH_STATS_RESOURCE, {"dispatched": 3, "skipped": 0, "failed": 0}),
        ],
    )

    monotonic_values = iter([100.0, 110.0])
    monkeypatch.setattr(
        "integration.pipeline.tasks.pipelines.mcmot_pipeline.time.monotonic",
        lambda: next(monotonic_values),
    )

    with caplog.at_level(logging.INFO, logger="pipeline-summary-test"):
        first_result = pipeline.execute(context)
        second_result = pipeline.execute(context)

    assert first_result.status == "mcmot_pipeline_done"
    assert second_result.status == "mcmot_pipeline_done"
    assert "開始任務：mcmot_pipeline" not in caplog.text
    assert caplog.text.count("pipeline_summary window=60s phase=working status=ok") == 1
    assert any(line.startswith("ingestion") for line in caplog.text.splitlines())
    assert any(line.startswith("event_dispatch") for line in caplog.text.splitlines())


def test_pipeline_summary_interval_follows_config(caplog) -> None:
    context = build_context()
    context.logger.setLevel(logging.INFO)
    context.config = SimpleNamespace(pipeline_summary_interval_seconds=15.0)
    pipeline = MCMOTPipelineTask(
        context,
        nodes=[
            DummyNode(INGESTION_STATS_RESOURCE, {"raw": 12, "events": 4, "dropped": 0}),
            DummyNode(MC_MOT_STATS_RESOURCE, {"events": 4, "tracked": 8, "global": 2}),
            DummyNode(FORMAT_STATS_RESOURCE, {"events": 4, "tracked": 8, "global": 2, "signal_groups": 1}),
            DummyNode(RULE_STATS_RESOURCE, {"warnings": 3}),
            DummyNode(EVENT_DISPATCH_STATS_RESOURCE, {"dispatched": 3, "skipped": 0, "failed": 0}),
        ],
    )

    with caplog.at_level(logging.INFO, logger="pipeline-summary-test"):
        result = pipeline.execute(context)

    assert result.status == "mcmot_pipeline_done"
    assert "pipeline_summary window=15s phase=working status=ok" in caplog.text
