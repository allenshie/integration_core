# Pipeline Architecture

本文件說明 integration core 預設的工作流程、可插拔節點與事件派送機制，協助子專案以 submodule 方式擴充。

## 預設 Working Pipeline

Working pipeline 固定由以下 `BaseTask` 組成：

1. **IngestionTask**：從 HTTP server 取得 edge 推理事件，正規化時間戳並過濾過期資料，可透過 `INGESTION_HANDLER_CLASS` 指定自訂 handler。
2. **MCMOTTask**：執行 MC-MOT 追蹤整合，預設使用 core 內建 engine，亦可透過 `TRACKING_ENGINE_CLASS` 切換實作。
3. **FormatConversionTask**（可關閉）：整理 ingestion/MCMOT 的結果為統一 `rules_payload`，可藉由 `FORMAT_TASK_ENABLED` 關閉或 `FORMAT_STRATEGY_CLASS` 指定策略。
4. **RuleEvaluationTask**：載入 `RULES_ENGINE_CLASS` 提供的規則引擎並回傳 `RuleEngineResult`。engine 可在 `context_updates` 寫入狀態或使用 `event_queue` 堆事件。
5. **EventDispatchTask**：將 selector/規則階段推送至 `event_queue` 的事件一次派送，預設 `DefaultEventDispatchEngine` 以 log 模擬寫入，可透過 `EVENT_DISPATCH_ENGINE_CLASS` 連接實際 API / DB。

子專案若需調整行為，優先透過上述 handler/engine 插槽覆寫；若需要完全不同的 pipeline，可使用 `PIPELINE_TASK_CLASSES` 註冊自訂 `BaseTask` 子類。

## Pipeline Registry 與 Selector

`InitPipelineTask` 在啟動時會：

1. 解析 `.env` 中的 `PIPELINE_TASK_CLASSES` 與 `PIPELINE_SLEEP_SECONDS`；
2. 實例化所有 pipeline Task，並將「預設 loop interval」一併註冊到 `PipelineRegistry`；
3. 建立 selector（`PIPELINE_SELECTOR_CLASS`，預設 `WorkingHoursSelector`）與事件佇列。

`PhaseTask` 每輪執行時會：

1. 呼叫 selector，取得 pipeline 名稱與 metadata（可包含 `sleep`、`phase_changed` 等）；
2. 從 registry 取得 pipeline 實例並執行；
3. 合併 selector metadata 與 pipeline 回傳 payload，若 payload 內沒有 `sleep`，則套用 registry 記錄的預設值；
4. 將結果交給 `WorkflowRunner`。runner 會根據 payload 的 `sleep` 調整下一輪間隔。

因此建議 selector 僅負責「決定 pipeline」與「在必要時設定 metadata」，而各 pipeline 自行決定是否在結果中設定 `sleep` 或事件。

## 事件派送流程

1. selector 或 RuleEngine 若要產生事件（例如 phase change、違規通知），可呼叫 `integration.pipeline.events.enqueue_event()` 將資料附加到 `event_queue`。
2. `EventDispatchTask` 會在當輪 pipeline 結束後讀取 queue、清空，再交給 `EVENT_DISPATCH_ENGINE_CLASS` 指定的 engine 處理。
3. 預設 `DefaultEventDispatchEngine` 僅在 log 中標示 `handlers` 與 payload，方便於尚未串接實際 API/DB 時驗證流程。子專案可繼承 `BaseEventDispatchEngine`，分別實作外部 API、內部資料庫等 handler。

事件 payload 可自行決定格式，只要包含 `handlers`（例如 `["external_api", "internal_db"]`）與 `data` 即可；engine 會依 handlers 做對應動作。

## 自訂 Pipeline 建議

- 若需要額外 pipeline（夜間巡檢、盤點、演示模式…），在 `.env` 設定 `PIPELINE_TASK_CLASSES=name=module:Class`。Class 只要繼承 `BaseTask` 並在 `run()` 中實作完整流程即可。
- 可在 `PIPELINE_SLEEP_SECONDS` 指定該 pipeline 預設的 loop interval；若需要動態調整，直接在 `TaskResult.payload` 加入 `sleep`。
- selector 在偵測場域狀態（例如門開關、排程時間）後，回傳對應 pipeline 名稱；若 pipeline 只需偶爾執行，metadata 裡可以同時設定 `sleep` 或自訂欄位給後續 Task 參考。

更多 plugin 點（ingestion/tracking/format/rules/dispatch）請參考 `README.md` 的「環境變數與插件」章節，以及對應模組內的程式碼。
