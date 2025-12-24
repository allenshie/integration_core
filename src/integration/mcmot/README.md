# MC-MOT 模組說明

MC-MOT（Multi-Camera Multi-Object Tracking）負責將 Edge 端的單相機推理結果轉換為倉庫全域座標系並維護 Global ID。此模組主要由以下元件構成：

- `config/`：Pydantic schema 與載入器，解析 `data/config/mcmot.config.yaml`。
- `core/coordinate/`：TPS / Homography Mapper，將局部像素座標映射到全域地圖。
- `core/mcmot/`：追蹤與匹配邏輯（Gallery、TrajectoryUtils、CostMatrix 等）。
- `services/mcmot_coordinator.py`：對外入口，整合座標轉換、軌跡分析與全域 ID 維護。
- `visualization/map_overlay.py`：可選的全域地圖可視化輔助工具。

## 配置檔案位置

預設設定檔為 `data/config/mcmot.config.yaml`，可透過環境變數 `MCMOT_CONFIG_PATH` 指向其他 YAML。主要欄位如下：

```yaml
system:
  coordinate_transform_mode: "tps"

tracking:
  trackable_classes:
    - "person"
  match_threshold: 1.0
  max_traj_loss: 1000.0
  distance_threshold_m: 5.0

map:
  image_path: "data/coordinate_models/global_map.png"
  pixel_width: 3840
  pixel_height: 1920
  width_meters: 120.0
  height_meters: 60.0

cameras:
  - camera_id: "camera1"
    edge_id: "cam01"
    name: "Camera 1"
    enabled: true
    coordinate_matrix_ckpt: "data/coordinate_models/cam1_tps_model.npz"
    ignore_polygons: "data/coordinate_models/ignore_polygons.npy"
```

### map 區段
- `image_path`：倉庫全域地圖影像，供可視化及像素/公尺換算使用。
- `pixel_width / pixel_height`：地圖影像解析度。
- `width_meters / height_meters`：實際物理尺寸，提供像素轉公尺的比例。

### cameras 區段
每個攝影機須描述與 Edge 事件對應方式與座標映射矩陣：

- `camera_id`：MC-MOT 內部名稱，也是全域地圖上使用的 ID。
- `edge_id`：Edge 事件中的 `camera_id`。若未設定，預設與 `camera_id` 相同。
- `coordinate_matrix_ckpt`：TPS/Homography 映射矩陣（`.npz`/`.npy`）。請將檔案放在 `data/coordinate_models/` 或對應路徑。
- `ignore_polygons`（可選）：忽略區域（`.npy`，內容為多邊形點陣列）。落在該區域的物件不會參與全域匹配或軌跡更新。
- `enabled`：可暫時停用某個攝影機設定。
- `color_hex`（可選）：在全局地圖可視化時使用的顏色（`#RRGGBB`）。若未設定會自動套用內建調色盤，圖例會顯示 `name` 或 `camera_id` 與顏色對照。

## 準備映射矩陣（npz）
1. 取得單相機畫面與倉庫全域地圖的對應點（至少 3~4 組 control points）。
2. 使用專案中的工具（如 `integration/mcmot/core/coordinate/tps_mapper.py`）或自訂腳本產生 TPS/Homography matrix，輸出成 `.npz` 檔放在 `data/coordinate_models/`。
3. 在 `mcmot.config.yaml` 的 `cameras[].coordinate_matrix_ckpt` 指向相對路徑，例如 `data/coordinate_models/cam1_tps_model.npz`。

## 忽略區域（npy）
若倉庫某些區域不需要追蹤（例如死角、鏡面反射區），可提供 `.npy` 檔案，內容為 `np.array([[x1, y1], [x2, y2], ...])`。MC-MOT 會將該多邊形載入並在軌跡分析時過濾該區域的物件。未設定 `ignore_polygons` 時則全部參與匹配。

## 可視化與驗證
- 啟用 `GLOBAL_MAP_VIS_ENABLED=1` 並正確設定地圖比例後，由 `GlobalMapRenderer` 將 global/local objects、距離與圖例一併繪製在 `map.image_path` 上。
- `GLOBAL_MAP_VIS_MODE` 可設定 `write`（預設，輸出檔案）、`show`（以 `cv2.imshow` 顯示）、`both`。
- `GLOBAL_MAP_VIS_CAMERAS` 可設定要疊加 local 物件的攝影機 ID（逗號分隔），並可搭配 `cameras[].color_hex` 調整每台相機的顏色。Legend 預設會顯示實際使用的攝影機；點大小會依地圖尺寸自動縮放。
- 產出的快照預設存於 `output/global_map/`，可快速檢查映射矩陣與追蹤是否正確。

## 故障排除
- **找不到配置檔**：確認 `MCMOT_CONFIG_PATH` 指向正確路徑，或將自訂 YAML 放在 `data/config/`。
- **TPS/Homography 載入失敗**：檢查 `.npz` 檔案是否包含 `map_x`, `map_y` 或對應矩陣，並確保路徑正確。
- **物件無法匹配**：可調整 `tracking.match_threshold`、`max_traj_loss` 或 `distance_threshold_m`，亦可透過全域地圖可視化查看實際位置。

如需新增攝影機，只要在 `cameras[]` 加入新的節點、提供對應的映射矩陣與（可選）忽略區域即可。
