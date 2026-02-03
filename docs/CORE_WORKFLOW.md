# Core Workflow (Default)

This document describes the default runtime behavior when using integration core
without custom plugins.

## Overview

The integration core uses a phase-aware scheduler to select a pipeline and then
executes that pipeline's tasks. When no custom classes are configured, the core
runs a single working phase and executes the built-in MC-MOT pipeline.

## Startup

1) `InitPipelineTask` loads `PIPELINE_SCHEDULE_PATH` and instantiates pipeline tasks.
2) Pipelines are registered in `pipeline_registry` as `phase -> pipeline`.

## Phase Resolution

`PhaseTask` asks the phase engine for the current phase:

- `PHASE_ENGINE_CLASS` unset: use `TimeBasedPhaseEngine`.
- `SCHEDULER_ENGINE_CLASS` unset: use `SinglePhaseSchedulerEngine`.

Default outcome: always resolve to a single `working` phase.

## Pipeline Execution

For `working` phase, the default pipeline is `MCMOTPipelineTask`, which runs:

1) `IngestionTask`: read latest edge events.
2) `MCMOTTask`: create/use `MCMOTEngine` and compute global tracking.
3) `FormatConversionTask`: normalize output payloads.
4) `RuleEvaluationTask`: run default rules engine.

## Loop

The workflow repeats every `LOOP_INTERVAL_SECONDS` seconds.

## Pipeline Schedule

`PIPELINE_SCHEDULE_PATH` 指向 `pipeline_schedule.json`，用於設定 phase 與 pipeline 的對應，
並可針對每個 phase 設定節流頻率（`interval_seconds`）。

### 範例

```json
{
  "pipelines": {
    "working": {
      "class": "integration.pipeline.tasks.pipelines.mcmot_pipeline:MCMOTPipelineTask"
    },
    "warehouse_modeling": {
      "class": "app.pipelines.warehouse_modeling:WarehouseModelingPipelineTask"
    }
  },
  "phases": {
    "working": { "pipeline": "working", "interval_seconds": 5 },
    "non_working": { "pipeline": "warehouse_modeling", "interval_seconds": 300 }
  }
}
```

說明：
- `phases.<name>.pipeline`：對應 `pipelines` 內的 pipeline 名稱。
- `phases.<name>.interval_seconds`：節流秒數（可省略，省略時每次 loop 都會執行）。

## Related Settings

- `PIPELINE_SCHEDULE_PATH`: required pipeline schedule JSON.
- `PHASE_ENGINE_CLASS`: optional custom phase engine.
- `SCHEDULER_ENGINE_CLASS`: optional custom scheduler engine.
- `RULES_ENGINE_CLASS`, `FORMAT_STRATEGY_CLASS`, etc.
