# Integration Daemon

整合端為常駐工作流程服務：接收 edge 事件、依據工作階段切換 pipeline，並將狀態回報至 monitoring。

## 文件

- [核心工作流程（分層與客製化）](docs/CORE_WORKFLOW.md)
- [環境變數說明（含協議範例）](docs/ENV.md)
- [Edge 通訊 Adapter 開發](docs/EDGE_COMM_ADAPTER.md)
- [Pipeline 排程設定](docs/CORE_WORKFLOW.md)
- [部署指南（Docker/K8s）](docs/DEPLOYMENT.md)
- [MC-MOT 模組說明](src/integration/mcmot/README.md)

## 快速開始

```bash
cd integration
cp .env.example .env
uv venv --python /usr/bin/python3.10
source .venv/bin/activate
uv pip install -e .
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

若作為子模組導入，建議以套件方式安裝（`pip/uv install -e .`），避免手動設定
`PYTHONPATH`。並於 `.env` 設定 `CONFIG_ROOT`、`PIPELINE_SCHEDULE_PATH` 及需要的
plugin class path。

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
SCHEDULER_ENGINE_CLASS=smart_warehouse_app.app.schedulers.iron_gate:IronGateSchedulerEngine
```

容器啟動時可直接執行：

```
python /app/my_project/integration/main.py
```
