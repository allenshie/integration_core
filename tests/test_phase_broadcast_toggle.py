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

from integration.pipeline.control.phase_task import PhaseTask
from integration.pipeline.control.scheduler import Phase


class DummyMonitor:
    def heartbeat(self, **kwargs) -> None:  # noqa: D401
        _ = kwargs


class DummyScheduler:
    def __init__(self, phase_name: str) -> None:
        self._phase_name = phase_name

    def current_phase(self, now=None) -> Phase:  # noqa: ANN001
        _ = now
        return Phase(name=self._phase_name, is_working_hours=True)


class DummyPipeline:
    def __init__(self) -> None:
        self.run_count = 0

    def execute(self, context) -> None:  # noqa: ANN001
        _ = context
        self.run_count += 1


class DummyPhaseChangeEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str | None, str]] = []

    def on_phase_change(self, old_phase: str | None, new_phase: str, context) -> None:  # noqa: ANN001
        _ = context
        self.calls.append((old_phase, new_phase))


class DummyMessagingClient:
    def __init__(self, publish_result: bool = True) -> None:
        self.publish_result = publish_result
        self.publish_calls: list[tuple[str, dict[str, object]]] = []

    def publish(self, route_key: str, payload: dict[str, object]) -> bool:
        self.publish_calls.append((route_key, payload))
        return self.publish_result


class DummyContext:
    def __init__(self, config, resources: dict[str, object] | None = None) -> None:
        self.config = config
        self._resources = dict(resources or {})
        self.logger = logging.getLogger("phase-broadcast-test")
        self.monitor = DummyMonitor()

    def get_resource(self, key: str):
        return self._resources.get(key)

    def set_resource(self, key: str, value) -> None:  # noqa: ANN001
        self._resources[key] = value

    def require_resource(self, key: str):
        value = self._resources.get(key)
        if value is None:
            raise KeyError(key)
        return value


def build_config(broadcast_enabled: bool):
    return SimpleNamespace(
        phase_task=SimpleNamespace(engine_class=None),
        phase_change=SimpleNamespace(engine_class=None),
        phase_messaging=SimpleNamespace(
            enabled=broadcast_enabled,
            backend="mqtt",
            heartbeat_seconds=300,
            channel="integration/phase",
        ),
    )


def build_context(broadcast_enabled: bool, messaging_client: DummyMessagingClient | None = None) -> DummyContext:
    pipeline = DummyPipeline()
    resources = {
        "scheduler": DummyScheduler("working"),
        "phase_task_change_engine": DummyPhaseChangeEngine(),
        "pipeline_registry": {"working": pipeline},
        "pipeline_policies": {},
    }
    if messaging_client is not None:
        resources["messaging_client"] = messaging_client
    return DummyContext(build_config(broadcast_enabled), resources)


def test_phase_broadcast_disabled_skips_publish_and_keeps_phase_change_single() -> None:
    messaging_client = DummyMessagingClient()
    context = build_context(False, messaging_client=messaging_client)
    task = PhaseTask()

    first_result = task.run(context)
    second_result = task.run(context)

    change_engine = context.get_resource("phase_task_change_engine")
    state = context.get_resource("phase_task_state")
    pipeline = context.get_resource("pipeline_registry")["working"]

    assert first_result.status == "phase_pipeline"
    assert second_result.status == "phase_pipeline"
    assert change_engine.calls == [(None, "working")]
    assert messaging_client.publish_calls == []
    assert state["last_phase"] == "working"
    assert state["last_publish_time"] == 0.0
    assert pipeline.run_count == 2


def test_phase_broadcast_enabled_publishes_once_for_same_phase() -> None:
    messaging_client = DummyMessagingClient()
    context = build_context(True, messaging_client=messaging_client)
    task = PhaseTask()

    first_result = task.run(context)
    second_result = task.run(context)

    change_engine = context.get_resource("phase_task_change_engine")
    state = context.get_resource("phase_task_state")
    pipeline = context.get_resource("pipeline_registry")["working"]

    assert first_result.status == "phase_pipeline"
    assert second_result.status == "phase_pipeline"
    assert change_engine.calls == [(None, "working")]
    assert len(messaging_client.publish_calls) == 1
    assert messaging_client.publish_calls[0][0] == "phase_publish"
    assert messaging_client.publish_calls[0][1]["phase"] == "working"
    assert state["last_phase"] == "working"
    assert state["last_publish_time"] > 0.0
    assert pipeline.run_count == 2


def test_phase_task_execute_suppresses_start_log(caplog) -> None:
    messaging_client = DummyMessagingClient()
    context = build_context(False, messaging_client=messaging_client)
    context.logger.setLevel(logging.DEBUG)
    task = PhaseTask()

    with caplog.at_level(logging.INFO, logger="phase-broadcast-test"):
        result = task.execute(context)

    assert result.status == "phase_pipeline"
    assert "開始任務：phase_controller" not in caplog.text
    assert "phase task: phase=working" in caplog.text


def test_phase_task_logs_state_only_once_for_same_phase(caplog) -> None:
    messaging_client = DummyMessagingClient()
    context = build_context(False, messaging_client=messaging_client)
    context.logger.setLevel(logging.DEBUG)
    task = PhaseTask()

    with caplog.at_level(logging.INFO, logger="phase-broadcast-test"):
        first_result = task.run(context)
        second_result = task.run(context)

    assert first_result.status == "phase_pipeline"
    assert second_result.status == "phase_pipeline"
    assert caplog.text.count("phase task: phase=working") == 1
