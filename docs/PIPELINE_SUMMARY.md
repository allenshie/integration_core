# pipeline_summary 輸出說明

`pipeline_summary` 是 integration core 週期性輸出的 pipeline 快照，用來同時觀察：

1. 這一輪 pipeline 是否真的有新資料。
2. 各 stage 的統計結果。
3. 在該時間窗口內的處理吞吐量。

## 輸出格式

典型輸出由三個區塊組成：

1. throughput block
2. latency block
3. stage table

```text
pipeline_summary window=60s phase=working status=ok
throughput | elapsed=10s | source_fps=15.00 | processed_fps=12.00 | duplicate_skip_fps=3.00 | active_batches=4 | idle_batches=2
latency | elapsed=10s | avg_active_ms=83.21
stage            | raw | events | dropped | duplicates | tracked | global | signal_groups | warnings | dispatched | skipped | failed
---------------- | --- | ------ | ------- | ---------- | ------- | ------ | ------------- | -------- | ---------- | ------- | ------
ingestion        | ...
mc_mot           | ...
format_conversion| ...
rule_evaluation  | ...
event_dispatch   | ...
```

### 第一行：summary header

`pipeline_summary window=<seconds> phase=<phase> status=<status>`

- `window`：這次 summary 的標稱週期秒數，來源是 `pipeline_summary_interval_seconds`。
- `phase`：目前 phase 名稱。
- `status`：
  - `ok`：pipeline 正常完成。
  - `idle`：本輪沒有足夠資料形成有意義的 stage 統計，屬於正常狀態，不代表錯誤。
  - `error`：pipeline 執行過程出現例外。

### throughput block

`throughput | elapsed=<seconds> | source_fps=<rate> | processed_fps=<rate> | duplicate_skip_fps=<rate> | active_batches=<count> | idle_batches=<count>`

- `elapsed`：實際用 `time.monotonic()` 算出的經過秒數，不一定和 `window` 完全相同。
- 欄位順序固定為 `elapsed` 在前，其他指標在後，方便機器與人工閱讀。
- `source_fps`：來源 edge 進入 app 的原始事件速率。
  - 對應 ingestion 前的 raw event 數量。
  - 代表接收端每秒收到多少筆事件。
- `processed_fps`：真正通過 ingestion 去重後、進入後續 pipeline 的有效事件速率。
  - 對應 ingestion 後保留下來的事件數量。
  - 這是 app 實際處理有效資料的速度。
- `duplicate_skip_fps`：被 ingestion 判定為重複、直接跳過的事件速率。
  - 通常來自相同 `camera_id + session_id + frame_seq` 的重送或重複送達。
- `active_batches`：這個報告窗口內，有新資料而真的往下跑 heavy pipeline 的次數。
- `idle_batches`：這個報告窗口內，因為沒有新資料而短路跳過的次數。

### latency block

`latency | elapsed=<seconds> | avg_active_ms=<milliseconds>`

- `elapsed`：和 throughput 相同的實際時間窗口。
- 欄位順序固定為 `elapsed` 在前，其他指標在後。
- `avg_active_ms`：這段窗口內，真的有新資料而跑完整條 heavy pipeline 的平均耗時。
  - 只在有 active batch 時才有意義。
  - 若這個窗口內沒有 active batch，會顯示 `-`。

## Stage 欄位說明

### ingestion

來源是 `EdgeEventStore` 的 raw events，經 `IngestionTask` 正規化後輸出。

- `raw`：原始收到的 event 數量。
- `events`：去重後保留下來的 event 數量。
- `dropped`：格式不合法、缺欄位、過期等原因被丟棄的 event 數量。
- `duplicates`：與上一輪已接受資料重複，因此被跳過的 event 數量。

### mc_mot

MC-MOT tracking 階段的統計。

- `events`：送入 tracking 的事件數量。
- `tracked`：tracking engine 產生的 tracked object 數量。
- `global`：全域物件數量。

### format_conversion

將 tracking 結果轉成 rules 可消費的 payload。

- `events`：本輪事件數量。
- `tracked`：本輪 tracked object 數量。
- `global`：本輪 global object 數量。
- `signal_groups`：格式化後 `overall_metadata.signal_groups` 的數量。

### rule_evaluation

規則引擎產出的警示數。

- `warnings`：本輪產生的 warning / rule events 數量。

### event_dispatch

事件派送階段的結果統計。

- `dispatched`：成功送出的事件數量。
- `skipped`：依規則判定不需送出的事件數量。
- `failed`：應送出但失敗的事件數量。

## 讀值方式

### 1. 先看 `status`

- `error`：先看 exception stack trace。
- `idle`：代表本輪沒有新資料，不需要當成異常。
- `ok`：正常完成。

### 2. 再看 throughput

- 想看來源送多快：看 `source_fps`。
- 想看 app 實際有效處理速度：看 `processed_fps`。
- 想看是否有大量重送或重複送達：看 `duplicate_skip_fps` 和 `duplicates`。

### 3. 最後看各 stage

- `ingestion` 是否有大量 `dropped` / `duplicates`。
- `mc_mot` 是否有正常產生 `tracked` / `global`。
- `rule_evaluation` 是否有 warning。
- `event_dispatch` 是否有大量 `failed`。

## 實例對照

### 1. 正常有新資料

```text
pipeline_summary window=60s phase=working status=ok
throughput | elapsed=10s | source_fps=15.00 | processed_fps=12.00 | duplicate_skip_fps=3.00 | active_batches=1 | idle_batches=0
latency | elapsed=10s | avg_active_ms=83.21
stage            | raw | events | dropped | duplicates | tracked | global | signal_groups | warnings | dispatched | skipped | failed
---------------- | --- | ------ | ------- | ---------- | ------- | ------ | ------------- | -------- | ---------- | ------- | ------
ingestion        | 15  | 12     | 0       | 3          | -       | -      | -             | -        | -          | -       | -
mc_mot           | -   | 12     | -       | -          | 8       | 4      | -             | -        | -          | -       | -
format_conversion| -   | 12     | -       | -          | 8       | 4      | 2             | -        | -          | -       | -
rule_evaluation  | -   | -      | -       | -          | -       | -      | -             | 5        | -          | -       | -
event_dispatch   | -   | -      | -       | -          | -       | -      | -             | -        | 5          | 0       | 0
```

判讀方式：
- `status=ok` 代表這輪有正常跑完。
- `source_fps=15.00` 表示 edge 送進來的原始速率。
- `processed_fps=12.00` 表示真正進入後續 pipeline 的有效速率。
- `duplicate_skip_fps=3.00` 表示有部分重複資料被 ingestion 排除。

### 2. 有重複送達，但仍有新資料

```text
pipeline_summary window=60s phase=working status=ok
throughput | elapsed=10s | source_fps=20.00 | processed_fps=8.00 | duplicate_skip_fps=12.00 | active_batches=1 | idle_batches=0
latency | elapsed=10s | avg_active_ms=125.44
stage            | raw | events | dropped | duplicates | tracked | global | signal_groups | warnings | dispatched | skipped | failed
---------------- | --- | ------ | ------- | ---------- | ------- | ------ | ------------- | -------- | ---------- | ------- | ------
ingestion        | 20  | 8      | 0       | 12         | -       | -      | -             | -        | -          | -       | -
```

判讀方式：
- `source_fps` 很高，但 `processed_fps` 明顯較低，通常代表重複送達或去重比例高。
- `duplicates` 是 ingestion 已判定為重複、所以沒有送進後續 pipeline 的資料量。

### 3. 沒有新資料，整條 heavy pipeline 被跳過

```text
pipeline_summary window=60s phase=working status=idle
throughput | elapsed=10s | source_fps=0 | processed_fps=0 | duplicate_skip_fps=0 | active_batches=0 | idle_batches=1
latency | elapsed=10s | avg_active_ms=-
stage            | raw | events | dropped | duplicates | tracked | global | signal_groups | warnings | dispatched | skipped | failed
---------------- | --- | ------ | ------- | ---------- | ------- | ------ | ------------- | -------- | ---------- | ------- | ------
ingestion        | 0   | 0      | 0       | 0          | -       | -      | -             | -        | -          | -       | -
```

判讀方式：
- `status=idle` 代表本輪沒有新資料，所以後續 MC-MOT / format / rules / dispatch 沒有跑。
- `idle_batches=1` 表示這個 window 內至少有一輪被短路跳過。
- 這不是錯誤，通常代表 app 的處理速度高於 edge 更新速度。

## 注意事項

- `window` 是 summary 的標稱輸出間隔，不是 throughput 的實際分母。
- throughput 的分母使用 `elapsed`，所以會比單純拿設定值除法更貼近真實跑速。
- `source_fps` 和 `processed_fps` 的差距，通常就是 ingestion 去重與過濾的效果。
- 如果 `idle_batches` 很高，代表 app 計算能力高於 edge 來源更新率，這是正常現象，不一定是異常。
