from __future__ import annotations

import logging
from types import SimpleNamespace

from smart_workflow import TaskResult

from integration.pipeline.tasks.base import QuietTaskBase
from integration.pipeline.tasks.pipelines.mcmot_pipeline import MCMOTPipelineTask
from integration.pipeline.tasks.summary import (
    EVENT_DISPATCH_STATS_RESOURCE,
    FORMAT_STATS_RESOURCE,
    INGESTION_STATS_RESOURCE,
    MC_MOT_STATS_RESOURCE,
    MATCHING_BROADCAST_STATS_RESOURCE,
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
    def __init__(
        self,
        resource_key: str,
        values: dict[str, int],
        payload: dict[str, object] | None = None,
    ) -> None:
        self._resource_key = resource_key
        self._values = values
        self._payload = payload

    def execute(self, context: DummyContext) -> TaskResult | None:
        store_stage_stats(context, self._resource_key, self._values)
        if self._payload is None:
            return None
        return TaskResult(status="ingestion_done", payload=self._payload)


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
        MATCHING_BROADCAST_STATS_RESOURCE,
        {"dispatched": 1, "skipped": 0, "failed": 0},
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
    assert any(line.startswith("matching_broadcast") for line in summary_lines)
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
            DummyNode(
                INGESTION_STATS_RESOURCE,
                {"raw": 12, "events": 4, "dropped": 0, "duplicates": 1},
                payload={
                    "raw": 12,
                    "events": 4,
                    "dropped": 0,
                    "duplicates": 1,
                    "has_new_data": True,
                },
            ),
            DummyNode(MC_MOT_STATS_RESOURCE, {"events": 4, "tracked": 8, "global": 2}),
            DummyNode(
                MATCHING_BROADCAST_STATS_RESOURCE,
                {"dispatched": 1, "skipped": 0, "failed": 0},
            ),
            DummyNode(FORMAT_STATS_RESOURCE, {"events": 4, "tracked": 8, "global": 2, "signal_groups": 1}),
            DummyNode(RULE_STATS_RESOURCE, {"warnings": 3}),
            DummyNode(EVENT_DISPATCH_STATS_RESOURCE, {"dispatched": 3, "skipped": 0, "failed": 0}),
        ],
    )

    monotonic_values = iter([100.0, 100.05, 110.0, 120.0, 120.05, 130.0])
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
    assert (
        "throughput | elapsed=10s | source_fps=1.20 | processed_fps=0.40 | "
        "duplicate_skip_fps=0.10 | active_batches=1 | idle_batches=0"
    ) in caplog.text
    assert "latency | elapsed=10s | avg_active_ms=50.00" in caplog.text
    summary_record = next(
        record.message
        for record in caplog.records
        if record.message.startswith("pipeline_summary window=60s phase=working status=ok")
    )
    assert any(line.startswith("ingestion") for line in summary_record.splitlines())
    assert any(line.startswith("event_dispatch") for line in summary_record.splitlines())


def test_pipeline_summary_interval_follows_config(caplog) -> None:
    context = build_context()
    context.logger.setLevel(logging.INFO)
    context.config = SimpleNamespace(pipeline_summary_interval_seconds=15.0)
    pipeline = MCMOTPipelineTask(
        context,
        nodes=[
            DummyNode(INGESTION_STATS_RESOURCE, {"raw": 12, "events": 4, "dropped": 0}),
            DummyNode(MC_MOT_STATS_RESOURCE, {"events": 4, "tracked": 8, "global": 2}),
            DummyNode(
                MATCHING_BROADCAST_STATS_RESOURCE,
                {"dispatched": 1, "skipped": 0, "failed": 0},
            ),
            DummyNode(FORMAT_STATS_RESOURCE, {"events": 4, "tracked": 8, "global": 2, "signal_groups": 1}),
            DummyNode(RULE_STATS_RESOURCE, {"warnings": 3}),
            DummyNode(EVENT_DISPATCH_STATS_RESOURCE, {"dispatched": 3, "skipped": 0, "failed": 0}),
        ],
    )

    with caplog.at_level(logging.INFO, logger="pipeline-summary-test"):
        result = pipeline.execute(context)

    assert result.status == "mcmot_pipeline_done"
    assert "pipeline_summary window=15s phase=working status=ok" in caplog.text
