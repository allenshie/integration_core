from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from smart_workflow import TaskResult

from integration.pipeline.tasks.nodes.ingestion.engine import DefaultIngestionEngine
from integration.pipeline.tasks.nodes.ingestion.task import IngestionTask
from integration.pipeline.tasks.pipelines.mcmot_pipeline import MCMOTPipelineTask


class DummyContext:
    def __init__(self, resources: dict[str, object] | None = None) -> None:
        self._resources = dict(resources or {})
        self.config = SimpleNamespace(
            edge_events=SimpleNamespace(max_age_seconds=60.0),
            edge_event_max_age_seconds=60.0,
            pipeline_summary_interval_seconds=60.0,
        )
        self.logger = logging.getLogger("ingestion-new-data-test")
        self.reported_success: list[str] = []
        self.reported_failure: list[tuple[str, str | None]] = []

    def get_resource(self, key: str):
        return self._resources.get(key)

    def set_resource(self, key: str, value) -> None:  # noqa: ANN001
        self._resources[key] = value

    def require_resource(self, key: str):
        if key not in self._resources:
            raise KeyError(key)
        return self._resources[key]

    def report_success(self, name: str) -> None:
        self.reported_success.append(name)

    def report_failure(self, name: str, detail: str | None = None) -> None:
        self.reported_failure.append((name, detail))


class _Store:
    def __init__(self, batches: list[list[dict[str, object]]]) -> None:
        self._batches = list(batches)

    def pop_all(self) -> list[dict[str, object]]:
        if not self._batches:
            return []
        return self._batches.pop(0)


class _RecordingNode:
    def __init__(self, result: TaskResult) -> None:
        self._result = result
        self.calls = 0

    def execute(self, context: DummyContext) -> TaskResult:
        _ = context
        self.calls += 1
        return self._result


def _edge_event(
    *,
    camera_id: str,
    session_id: str,
    frame_seq: int,
    capture_ts: datetime,
    publish_offset_ms: int = 20,
) -> dict[str, object]:
    return {
        "camera_id": camera_id,
        "session_id": session_id,
        "frame_seq": frame_seq,
        "capture_ts": capture_ts.isoformat(),
        "timestamp": (capture_ts + timedelta(milliseconds=publish_offset_ms)).isoformat(),
        "detections": [
            {
                "track_id": frame_seq,
                "class_name": "person",
                "bbox": [1, 2, 3, 4],
                "bbox_confidence_score": 0.9,
            }
        ],
        "models": ["detect"],
    }


def test_default_ingestion_engine_detects_new_frames_per_camera() -> None:
    context = DummyContext()
    engine = DefaultIngestionEngine(context=context)
    capture_1 = datetime(2026, 6, 4, 8, 15, 0, tzinfo=timezone.utc)
    capture_2 = datetime(2026, 6, 4, 8, 15, 1, tzinfo=timezone.utc)

    first = engine.process(
        context,
        [
            _edge_event(camera_id="cam-01", session_id="sess-a", frame_seq=1, capture_ts=capture_1),
            _edge_event(camera_id="cam-02", session_id="sess-b", frame_seq=3, capture_ts=capture_2),
        ],
    )

    assert first.has_new_data is True
    assert first.dirty_camera_ids == ["cam-01", "cam-02"]
    assert [event["camera_id"] for event in first.events] == ["cam-01", "cam-02"]
    assert [event["frame_seq"] for event in first.events] == [1, 3]

    second = engine.process(
        context,
        [
            _edge_event(camera_id="cam-01", session_id="sess-a", frame_seq=1, capture_ts=capture_1),
            _edge_event(camera_id="cam-02", session_id="sess-b", frame_seq=4, capture_ts=capture_2 + timedelta(seconds=1)),
        ],
    )

    assert second.has_new_data is True
    assert second.dirty_camera_ids == ["cam-02"]
    assert second.duplicate_count == 1
    assert [event["camera_id"] for event in second.events] == ["cam-02"]
    assert second.events[0]["frame_seq"] == 4


def test_ingestion_task_preserves_latest_snapshot_when_batch_is_duplicate() -> None:
    capture_ts = datetime(2026, 6, 4, 8, 20, 0, tzinfo=timezone.utc)
    event = _edge_event(camera_id="cam-01", session_id="sess-a", frame_seq=7, capture_ts=capture_ts)
    context = DummyContext(
        resources={
            "edge_event_store": _Store([[event], [event]]),
        }
    )
    task = IngestionTask(context)

    first_result = task.run(context)
    first_snapshot = context.get_resource("edge_events_latest")

    second_result = task.run(context)

    assert first_result.payload["has_new_data"] is True
    assert first_snapshot is not None
    assert len(first_snapshot) == 1
    assert first_snapshot[0]["camera_id"] == "cam-01"
    assert first_snapshot[0]["session_id"] == "sess-a"
    assert first_snapshot[0]["frame_seq"] == 7
    assert second_result.payload["has_new_data"] is False
    assert second_result.payload["duplicates"] == 1
    assert context.get_resource("edge_events_latest") == first_snapshot
    assert context.get_resource("pipeline_has_new_data") is False
    assert context.get_resource("pipeline_dirty_camera_ids") == []


def test_mcmot_pipeline_skips_followup_nodes_when_ingestion_has_no_new_data() -> None:
    context = DummyContext()
    ingestion = _RecordingNode(TaskResult(status="ingestion_done", payload={"has_new_data": False}))
    second = _RecordingNode(TaskResult(status="mc_mot_done"))
    third = _RecordingNode(TaskResult(status="rules_done"))
    pipeline = MCMOTPipelineTask(context, nodes=[ingestion, second, third])

    result = pipeline.run(context)

    assert result.status == "mcmot_pipeline_skipped"
    assert ingestion.calls == 1
    assert second.calls == 0
    assert third.calls == 0
