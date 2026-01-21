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

## Related Settings

- `PIPELINE_SCHEDULE_PATH`: required pipeline schedule JSON.
- `PHASE_ENGINE_CLASS`: optional custom phase engine.
- `SCHEDULER_ENGINE_CLASS`: optional custom scheduler engine.
- `RULES_ENGINE_CLASS`, `FORMAT_STRATEGY_CLASS`, etc.
