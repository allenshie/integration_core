# Integration Daemon

整合端為常駐工作流程服務：接收 edge 事件、依據工作階段切換 pipeline，並將狀態回報至 monitoring。

## 文件

- [Core Workflow（預設流程）](docs/CORE_WORKFLOW.md)
- [環境變數說明](docs/ENV.md)
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
`PIPELINE_SCHEDULE_PATH` 及需要的 plugin class path。
