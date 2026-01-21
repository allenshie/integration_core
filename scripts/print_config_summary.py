from __future__ import annotations

import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


def _setup_paths(repo_root: Path) -> None:
    src_path = repo_root / "src"
    for path in (repo_root, src_path):
        str_path = str(path)
        if str_path not in sys.path:
            sys.path.insert(0, str_path)


def _class_name(path: str) -> str:
    if ":" in path:
        return path.split(":", 1)[1]
    return path.rsplit(".", 1)[-1]


def _try_import(class_path: str):
    try:
        from integration.pipeline.schedule import load_task_class

        cls = load_task_class(class_path)
        return cls
    except Exception as exc:  # pragma: no cover - diagnostics only
        return f"import_error: {exc}"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    _setup_paths(repo_root)

    if load_dotenv is not None:
        load_dotenv(repo_root / ".env")

    from integration.config.settings import load_config
    from integration.pipeline.schedule import load_pipeline_schedule

    config = load_config()
    if not config.pipeline_schedule_path:
        print("PIPELINE_SCHEDULE_PATH not set.")
        return 1

    pipelines, phases = load_pipeline_schedule(config.pipeline_schedule_path)

    scheduler_engine = getattr(getattr(config, "scheduler", None), "engine_class", None)
    phase_engine = getattr(getattr(config, "phase_task", None), "engine_class", None)

    print("Config summary:")
    print(f"- scheduler_engine: {_class_name(scheduler_engine) if scheduler_engine else 'SinglePhaseSchedulerEngine'}")
    print(f"- phase_engine: {_class_name(phase_engine) if phase_engine else 'TimeBasedPhaseEngine'}")
    print(f"- pipeline_schedule: {config.pipeline_schedule_path}")
    print()
    print("Pipeline registry (from schedule):")
    for name, spec in pipelines.items():
        resolved = _try_import(spec.class_path)
        if isinstance(resolved, str):
            print(f"- {name}: {_class_name(spec.class_path)} ({resolved})")
            continue
        print(f"- {name}: {resolved.__name__}")
        describe = getattr(resolved, "describe_flow", None)
        if callable(describe):
            try:
                flow = describe(config)
                if flow:
                    print(f"  flow: {flow}")
            except Exception as exc:  # pragma: no cover
                print(f"  flow: error ({exc})")
    print()
    print("Phases:")
    for phase, pipeline in phases.items():
        print(f"- {phase} -> {pipeline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
