# 環境變數說明

此文件列出可選環境變數與用途。`.env.example` 僅保留核心必填項；
其餘變數請在需要時加入 `.env`。

## 排程與工作階段

- `PHASE_ENGINE_CLASS`：PhaseEngine 類別路徑（`module:Class`）。用於自訂 phase 切換邏輯。
- `SCHEDULER_ENGINE_CLASS`：SchedulerEngine 類別路徑（`module:Class`）。用於自訂當前 phase 判斷。
- `PHASE_STABLE_SECONDS`：整數秒。`DebouncedPhaseEngine` 的穩定時間窗，預設 `180`。
- `EDGE_EVENT_STALE_SECONDS`：整數秒。超過此秒數未收到新 edge 事件視為 stale，預設 `0`（關閉）。
- `EDGE_EVENT_STALE_MODE`：`freeze` 或 `unknown`。stale 時行為：保留或切到未知。
- `EDGE_EVENT_UNKNOWN_PHASE`：字串。stale mode 為 `unknown` 時使用的 phase 名稱。

## Pipeline 插件

- `INGESTION_ENGINE_CLASS`：Ingestion engine 類別路徑（`module:Class`）。
- `TRACKING_ENGINE_CLASS`：Tracking handler 類別路徑（`module:Class`）。
- `FORMAT_STRATEGY_CLASS`：Format engine 類別路徑（`module:Class`）。
- `RULES_ENGINE_CLASS`：Rule engine 類別路徑（`module:Class`）。
- `RULES_DETAIL`：字串。規則節點額外描述（僅 log）。

## MC-MOT

- `MCMOT_ENABLED`：`0/1` 或 `true/false`。是否啟用 MC-MOT。預設 `1`。
- `MCMOT_CONFIG_PATH`：字串路徑。MC-MOT 設定檔位置（相對於 integration root）。

## 視覺化（可選）

只有需要輸出全域地圖時才需設定：

- `GLOBAL_MAP_VIS_ENABLED`：`0/1`。
- `GLOBAL_MAP_VIS_MODE`：`write/show/both`。
- `GLOBAL_MAP_VIS_OUTPUT`：輸出資料夾路徑。
- `GLOBAL_MAP_VIS_WINDOW`：視窗名稱。
- `GLOBAL_MAP_VIS_RADIUS`：整數像素。
- `GLOBAL_MAP_VIS_LABEL_SCALE`：浮點數。
- `GLOBAL_MAP_VIS_LABEL_THICKNESS`：整數。
- `GLOBAL_MAP_VIS_SHOW_ID`：`0/1`。
- `GLOBAL_MAP_VIS_SHOW_CLASS`：`0/1`。
- `GLOBAL_MAP_VIS_CAMERAS`：逗號分隔字串，例如 `cam01,cam02`。
- `GLOBAL_MAP_VIS_SHOW_LEGEND`：`0/1`。
- `GLOBAL_MAP_VIS_GLOBAL_COLOR`：色碼字串 `#RRGGBB`。
- `GLOBAL_MAP_VIS_CLASS_COLORS`：`class:#RRGGBB,class2:#RRGGBB`。
- `GLOBAL_MAP_VIS_GLOBAL_RADIUS_RATIO`：浮點數。
- `GLOBAL_MAP_VIS_LOCAL_RADIUS_RATIO`：浮點數。

## Edge 事件

- `EDGE_EVENT_MAX_AGE`：整數秒。超過此秒數的事件會被丟棄。
- `EDGE_EVENT_BACKEND`：`http` 或 `mqtt`。預設 `http`。
- `EDGE_EVENTS_MQTT_TOPIC`：字串。MQTT 模式下使用的 topic，預設 `edge/events`。

## MQTT 廣播

- `MQTT_ENABLED`：`0/1`。是否啟用 MQTT 發佈工作階段。
- `MQTT_HOST`：字串。MQTT broker host，預設 `localhost`。
- `MQTT_PORT`：整數。MQTT broker port，預設 `1883`。
- `PHASE_MQTT_TOPIC`：字串。工作階段發布 topic，預設 `integration/phase`。
- `MQTT_QOS`：整數（0/1/2）。建議 `1`。
- `MQTT_RETAIN`：`0/1`。是否保留最後狀態，建議 `1`。
- `MQTT_HEARTBEAT_SECONDS`：整數秒。狀態心跳重送間隔，預設 `600`。
- `MQTT_CLIENT_ID`：字串。MQTT client id（可選）。

## 協議設定範例

### phase 發佈（MQTT）

```
MQTT_ENABLED=1
MQTT_HOST=localhost
MQTT_PORT=1883
PHASE_MQTT_TOPIC=integration/phase
MQTT_QOS=1
MQTT_RETAIN=1
MQTT_HEARTBEAT_SECONDS=600
```

### edge events 接收（HTTP / MQTT）

```
# HTTP 模式
EDGE_EVENT_BACKEND=http
EDGE_EVENT_HOST=0.0.0.0
EDGE_EVENT_PORT=9000

# MQTT 模式
EDGE_EVENT_BACKEND=mqtt
EDGE_EVENTS_MQTT_TOPIC=edge/events
MQTT_HOST=localhost
MQTT_PORT=1883
```

## 執行節奏

- `LOOP_INTERVAL_SECONDS`：整數秒。主循環間隔。
- `RETRY_BACKOFF_SECONDS`：整數秒。錯誤重試退避時間。
- `CONFIG_SUMMARY`：`0/1`。啟動時輸出配置摘要（engine/pipeline 設定）。
- `PIPELINE_SCHEDULE_PATH`：pipeline schedule 設定檔路徑。格式與範例請見 `docs/CORE_WORKFLOW.md`。
- `CONFIG_ROOT`：相對路徑解析基準（建議設為主專案根目錄）；未設定時回退到 integration root。

## Iron Gate Scheduler（專案插件）

僅在使用 `IronGateSchedulerEngine` 時需要：

- `EDGE_GATE_CLASS`：字串。鐵門類別名稱，預設 `iron_gate`。
- `EDGE_WORKING_PHASE`：字串。對應開門時的 phase 名稱，預設 `working`。
- `EDGE_NON_WORKING_PHASE`：字串。對應關門時的 phase 名稱，預設 `non_working`。
