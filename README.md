# Integration Daemon

整合端為常駐工作流程服務：接收 edge 事件、依據工作階段切換 pipeline，並將狀態回報至 monitoring。

## 文件

- [Core Workflow（預設流程）](docs/CORE_WORKFLOW.md)
- [環境變數說明（含協議範例）](docs/ENV.md)
- [Pipeline Schedule 設定](docs/CORE_WORKFLOW.md#pipeline-schedule)
- [Deployment Guide（Docker/K8s）](docs/DEPLOYMENT.md)
- [MC-MOT 模組說明](src/integration/mcmot/README.md)

## 快速開始

```bash
cd integration
cp .env.example .env
uv venv --python /usr/bin/python3.10
source .venv/bin/activate
uv pip install -r requirements.txt
python main.py
```

## 安裝成套件（建議）

若作為子模組或需要在 Docker/K8s 使用，建議安裝成套件（避免手動設定 PYTHONPATH）：

```bash
cd integration
pip install -e .
```

## 目錄結構

```
integration/
├── main.py
├── .env(.example)
├── src/integration/
├── data/
└── README.md
```

## 子專案使用

若作為子模組導入，請確保 `integration/src` 在 `PYTHONPATH`，並於 `.env` 設定
`CONFIG_ROOT`、`PIPELINE_SCHEDULE_PATH` 及需要的 plugin class path。

### 範例（主專案使用）

主專案目錄結構：

```
my_project/
├── integration/  # core 子模組
├── pipeline_schedule.json
└── .env
```

主專案 `.env`：

```
CONFIG_ROOT=/app/my_project
PIPELINE_SCHEDULE_PATH=pipeline_schedule.json
PHASE_ENGINE_CLASS=integration.pipeline.control.phase_engine:DebouncedPhaseEngine
SCHEDULER_ENGINE_CLASS=app.schedulers.iron_gate:IronGateSchedulerEngine
```

容器啟動時需確保 `integration/src` 可被 import，例如：

```
export PYTHONPATH=/app/my_project/integration/src:$PYTHONPATH
python /app/my_project/integration/main.py
```
