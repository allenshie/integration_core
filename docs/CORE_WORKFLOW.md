# 核心工作流程（分層與客製化）

本文件目標是協助使用 integration core 的開發者快速理解：
1. 系統整體如何運作。
2. 需求變動時該從哪一層進行客製化。
3. 如何替換預設實作並驗證是否生效。

## 最短上手路徑

1. 先看「第一層：Workflow Runner 外層流程」，建立全局觀。  
2. 再看「第二層：Loop Task（PhaseTask）」，理解 phase 切換與 pipeline 選擇。  
3. 最後看「可客製化點與替換方式」，依需求選擇調整點。  

若你只需要修改「某個 phase 跑哪條 pipeline」，優先調整 `pipeline_schedule.json`；
若你要改行為邏輯，再替換對應 `*_ENGINE_CLASS`。

## 第一層：Workflow Runner 外層流程

外層流程可視為三步驟：

1. `set store`  
啟動 edge 通訊 adapter，持續接收 edge 推理結果並更新 store/context。  
同一個 adapter 同時負責 phase publish（預設跟隨 `EDGE_EVENT_BACKEND`，可由 `PHASE_PUBLISH_BACKEND` 覆寫）。

2. `build_workflow`  
建立兩個核心任務：
- `InitPipelineTask`：初始化 pipeline，建立 phase 與 pipeline 的映射註冊。
- `LoopTask`（內含 `PhaseTask`）：主循環任務。

3. `WorkflowRunner.run`  
先執行初始化任務；初始化完成後，才會進入 loop 任務並重複執行。

## 第二層：Loop Task（PhaseTask）流程

每一輪 loop 主要邏輯如下：

1. 執行 `BasePhaseEngine`（或其子類）取得當前 phase。  
2. 回報 heartbeat（依設定的 publish backend）。  
3. 若 phase 改變，觸發 phase change 事件處理（如通知外部系統）。  
4. 依當前 phase 從 registry 取得對應 pipeline task。  
5. 執行該 pipeline task。  

主循環間隔由 `LOOP_INTERVAL_SECONDS` 控制。

## 第三層：Pipeline Task 與 Task/Engine 關係

在 integration core 中：

1. phase 只決定「執行哪條 pipeline task」。  
2. pipeline task 由多個節點 `Task` 組成（例如 ingestion、tracking、rules、dispatch）。  
3. `Task` 本身是流程節點封裝；實際業務邏輯由對應 `Engine` 類執行。  

可將職責理解為：
- `Workflow/Task`：編排與流程控制。
- `Engine`：可替換的實作邏輯（插件化擴充點）。

## Pipeline 排程設定

`PIPELINE_SCHEDULE_PATH` 指向 `pipeline_schedule.json`，用於定義：
1. 有哪些可用 pipelines。
2. 每個 phase 要執行哪條 pipeline。
3. 每個 phase 的節流頻率（`interval_seconds`）。

### 範例

```json
{
  "pipelines": {
    "working": {
      "class": "integration.pipeline.tasks.pipelines.mcmot_pipeline:MCMOTPipelineTask"
    },
    "warehouse_modeling": {
      "class": "smart_warehouse_app.app.pipelines.warehouse_modeling:WarehouseModelingPipelineTask"
    }
  },
  "phases": {
    "working": { "pipeline": "working", "interval_seconds": 5 },
    "non_working": { "pipeline": "warehouse_modeling", "interval_seconds": 300 }
  }
}
```

說明：
- `phases.<name>.pipeline`：對應 `pipelines` 內 pipeline 名稱。
- `phases.<name>.interval_seconds`：該 phase 的執行節流秒數（可省略）。

## 可客製化點與替換方式

### 1) Phase 判斷策略（何時切 phase）

- 可調整點：`PHASE_ENGINE_CLASS`、`SCHEDULER_ENGINE_CLASS`
- 適用情境：需要根據場域訊號（例如設備狀態）判斷工作階段，而非固定時間窗。
- 風險：phase 名稱與 schedule 不一致時會找不到對應 pipeline。

### 2) Phase 對應 Pipeline（每個 phase 跑什麼）

- 可調整點：`pipeline_schedule.json`
- 適用情境：working/non_working 要跑不同 pipeline 或不同執行頻率。
- 優點：不改程式碼即可生效，是最低風險調整入口。

### 3) 節點實作邏輯（Task 背後的 Engine）

- 可調整點：各種 `*_ENGINE_CLASS`（如 `RULES_ENGINE_CLASS`、`EVENT_DISPATCH_ENGINE_CLASS`）
- 適用情境：需要替換預設邏輯以符合專案場景需求。
- 重點：Task 不需重寫，通常只替換 Engine 即可。

### 4) 輸入/輸出協議

- 可調整點：edge events backend、phase publish backend、dispatch engine。
- 適用情境：對接不同來源（HTTP/MQTT）或不同下游 API 協議。
- 預設策略：`PHASE_PUBLISH_BACKEND` 未設定時，會跟隨 `EDGE_EVENT_BACKEND`，讓 store 與 phase publish 使用相同協議。
- 新增協議 adapter 的步驟請見：`docs/EDGE_COMM_ADAPTER.md`。

## 客製化決策指南

1. 需求是「切換時機不對」：先調 `PHASE_ENGINE_CLASS` / `SCHEDULER_ENGINE_CLASS`。  
2. 需求是「某 phase 應跑另一條流程」：改 `pipeline_schedule.json`。  
3. 需求是「流程節點行為要改」：替換該節點對應 `*_ENGINE_CLASS`。  
4. 需求是「外部協議不同」：調整 ingestion/dispatch/publish 對應 engine 或 backend 設定。  

## 客製化替換步驟模板

1. 建立自訂 Engine 類（例如 `my_project.engines.xxx:MyXxxEngine`）。  
2. 透過 `.env` 設定對應 `*_ENGINE_CLASS`（或修改 `pipeline_schedule.json`）。  
3. 啟動服務，確認 log 顯示已載入自訂 class path。  
4. 觀察節點輸入輸出與下游回應，確認行為符合預期。  

## 驗證清單與回退建議

### 驗證清單

1. 啟動時確認 config summary（engine class / schedule）正確。  
2. phase 切換時確認 heartbeat 與 phase change 事件正常。  
3. 當前 phase 執行到預期 pipeline task。  
4. 關鍵節點（rules/dispatch 等）有正確輸出與錯誤處理。  

### 回退建議

1. 保留上一版 `pipeline_schedule.json` 與 `.env`。  
2. 若新 Engine 行為異常，先切回預設 `*_ENGINE_CLASS`。  
3. 若 phase mapping 異常，先回退 schedule，再排查 phase 名稱與鍵值。  

## 相關設定索引

- `PIPELINE_SCHEDULE_PATH`：pipeline 排程 JSON 路徑（必填）。  
- `PHASE_ENGINE_CLASS`：phase engine 類別路徑（可選）。  
- `SCHEDULER_ENGINE_CLASS`：scheduler engine 類別路徑（可選）。  
- `RULES_ENGINE_CLASS`、`FORMAT_STRATEGY_CLASS`、`EVENT_DISPATCH_ENGINE_CLASS` 等：節點實作替換入口。  
