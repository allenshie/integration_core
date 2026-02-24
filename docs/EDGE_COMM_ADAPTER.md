# Edge 通訊 Adapter 開發指南

本文件說明如何在 integration core 新增「edge 通訊協議」。

核心原則：
1. 對外流程只依賴 `EdgeCommAdapter`，不直接耦合 MQTT/HTTP 細節。
2. 實際協議能力由 `smart_messaging_core.MessagingClient` 提供。
3. 只有 `MessagingClient` 支援的 backend 才能直接接入；否則需自行封裝客戶端。

---

## 1. 介面契約

所有協議 adapter 都要實作：

- `start_event_ingestion(on_event)`：啟動 edge 推理結果監聽，收到資料後呼叫 `on_event(dict)`。
- `publish_phase(phase_name, timestamp)`：發布當前 phase。
- `stop()`：釋放資源（若有 server/thread/connection）。

參考位置：
- `src/integration/comm/base.py`

---

## 2. 先建立協議 Config 類

在 `src/integration/config/settings.py` 加入協議設定類與 `.env` 對應鍵。

建議至少包含：
- backend 型別（例如 `mqtt/http/xxx`）
- 連線資訊（host/port/base_url/token）
- topic/path
- timeout/retry

範例（示意）：

```python
@dataclass
class XxxProtocolConfig:
    enabled: bool = _env_bool("XXX_ENABLED", False)
    host: str = os.getenv("XXX_HOST", "localhost")
    port: int = int(os.getenv("XXX_PORT", "1234"))
```

---

## 3. 建立 Adapter 類（繼承 EdgeCommAdapter）

新增檔案例如：
- `src/integration/comm/xxx_adapter.py`

實作重點：
1. 在 `__init__` 建立協議 client（可使用 `MessagingClient` 或自有 SDK）。
2. `start_event_ingestion` 訂閱/接收 edge 事件，回呼 `on_event(payload)`。
3. `publish_phase` 對 edge 發布 phase 資訊，回傳 `bool`。
4. `stop` 做必要清理。

範例（示意）：

```python
class XxxEdgeCommAdapter(EdgeCommAdapter):
    def __init__(self, config, logger=None) -> None:
        self._cfg = config
        self._logger = logger
        self._client = MessagingClient(...)

    def start_event_ingestion(self, on_event):
        self._client.subscribe(..., on_event)

    def publish_phase(self, phase_name: str, timestamp: float) -> bool:
        return self._client.publish(..., {"phase": phase_name, "timestamp": timestamp})

    def stop(self) -> None:
        return None
```

---

## 4. 在 Factory 註冊協議

更新：
- `src/integration/comm/factory.py`

將 backend 字串映射到你的 adapter 類。

範例（示意）：

```python
if backend == "xxx":
    return XxxEdgeCommAdapter(config, logger=logger)
```

---

## 5. 啟動流程如何使用

`main.py` 只做三件事：
1. `build_edge_comm_adapter(config)`
2. `adapter.start_event_ingestion(store.add_event)`
3. `context.set_resource("edge_comm_adapter", adapter)`

`PhaseTask` 透過：
- `edge_comm_adapter.publish_phase(...)`

這樣可確保 ingestion 與 phase publish 由同一抽象層管理。

---

## 6. .env 設定規則

基礎規則：
1. `EDGE_EVENT_BACKEND` 決定 ingestion adapter 類型。
2. `PHASE_PUBLISH_BACKEND` 空值時會跟隨 `EDGE_EVENT_BACKEND`。
3. 若要分離協議，顯式設定 `PHASE_PUBLISH_BACKEND`。

---

## 7. 驗證清單

1. 啟動 log 出現 adapter 初始化訊息。  
2. edge 事件可進入 `IngestionTask`（`raw_count` 有值）。  
3. phase 切換時 `publish_phase` 成功，edge 端收到 phase。  
4. backend 設定錯誤時有清楚 warning（非靜默失敗）。  

---

## 8. 常見錯誤

1. `.env` backend 值與 factory 不一致（例如填 `mqtts` 但 factory 只支援 `mqtt`）。  
2. 只做 ingestion，忘記實作 `publish_phase`。  
3. `publish_phase` 回傳非布林，導致 `PhaseTask` 判斷失準。  
4. 忘記在 `stop()` 清理 server/thread（長時間運行會累積資源）。  
