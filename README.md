# YouTube 即時姿態辨識／行為事件分析系統

以 YOLOv8-Pose 為核心，對 YouTube 影片／直播進行即時人物偵測、姿態關鍵點估測、
多目標追蹤，並在此之上做行為與事件分析（人數統計／異常偵測／ROI 區域），
事件會寫入資料庫並可透過 Streamlit Dashboard 視覺化、觸發告警、產生 AI 摘要報告。

## Workflow

```
YouTube Video / Live
        ↓
   Stream Capture
        ↓
   YOLOv8-Pose
        ↓
  Person Detection
        ↓
  Pose Keypoints
        ↓
   Person Tracking
        ↓
  行為／事件分析
        ↓
┌───────┼───────┐
↓       ↓       ↓
人數統計 異常偵測  ROI區域
└───────┼───────┘
        ↓
   Event Engine
        ↓
  Database / Log
        ↓
Streamlit Dashboard
        ↓
 Alert / AI Report
```

## 專案結構

```
yt_pose_project/
├── config.yaml              # 全域設定（YouTube 網址、模型、ROI、閾值...）
├── requirements.txt
├── main.py                  # Pipeline 進入點（Capture→Detect→Track→Analyze→Event→DB）
├── src/
│   ├── config_loader.py     # 讀取 config.yaml
│   ├── geometry.py          # ROI 幾何工具 (point-in-polygon 等)
│   ├── constants.py         # COCO 17 關鍵點索引定義
│   ├── types.py             # Detection / TrackState / Event 資料結構
│   ├── stream_capture.py    # YouTube Video/Live → Stream Capture
│   ├── pose_detector.py     # YOLOv8-Pose → Person Detection → Pose Keypoints
│   ├── tracker.py           # Person Tracking
│   ├── behavior_analysis.py # 行為/事件分析（協調三個子模組）
│   ├── people_counter.py    #   ├─ 人數統計
│   ├── anomaly_detector.py  #   ├─ 異常偵測（跌倒 / 異常快速移動）
│   ├── roi_manager.py       #   └─ ROI 區域（進出/擁擠/徘徊）
│   ├── event_engine.py      # Event Engine（去重、分級、寫入、告警）
│   ├── database.py          # Database / Log（SQLite）
│   └── alert.py             # Alert / AI Report
├── dashboard/
│   └── app.py                # Streamlit Dashboard（讀取同一份 SQLite）
├── notebooks/
│   └── demo_pipeline.ipynb   # 互動式 Demo / 單張畫面測試（原上傳檔案的重製版）
├── data/                      # SQLite 資料庫存放處（執行後自動產生 events.db）
├── logs/                      # 即時標註畫面存放處（latest_frame.jpg）
└── models/                    # YOLOv8-Pose 權重檔（可選，未放置則自動下載）
```

## 安裝

建議使用 Python 3.10+ 的虛擬環境：

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> 若要在無 GUI 的伺服器上跑（不開 cv2 視窗），OpenCV 用一般的 `opencv-python`
> 即可（本專案已在 requirements.txt 指定含 GUI 支援的版本）；純伺服器/容器
> 部署可自行改用 `opencv-python-headless` 並搭配 `main.py --no-display`。

## 設定

打開 `config.yaml`，至少確認以下幾項：

1. `source.youtube_url`：要分析的 YouTube 影片或直播網址
2. `model.weights`：YOLOv8-Pose 權重，預設 `yolov8n-pose.pt`（速度快，精度較低），
   也可換成 `yolov8s/m/l/x-pose.pt` 以換取更高精度
3. `behavior.roi.zones`：依你的畫面座標系統定義 ROI 多邊形與容量上限
4. `behavior.anomaly_detection`：跌倒/快速移動/徘徊的判斷閾值，建議先用預設值
   跑一段時間，再依實際場域微調
5. `alert.webhook_url`：若要串接 Slack/LINE Notify/Discord 等告警管道，填入其
   webhook 網址即可（留空則只印到終端機）

## 執行

### 1. 啟動偵測 Pipeline（背景／伺服器模式）

```bash
python main.py --no-display
```

會持續讀取 YouTube 串流、跑 YOLOv8-Pose、追蹤、行為分析，並把事件與人數統計
寫入 `data/events.db`，同時每隔幾秒把標註畫面存到 `logs/latest_frame.jpg`。

若在有 GUI 的本機環境，想直接看到即時標註視窗，可省略 `--no-display`：

```bash
python main.py
```

也可以在執行時覆寫設定檔內的網址：

```bash
python main.py --url "https://www.youtube.com/watch?v=xxxxxxxx" --no-display
```

### 2. 啟動 Dashboard

另開一個終端機（Pipeline 持續在背景跑），執行：

```bash
streamlit run dashboard/app.py
```

Dashboard 會顯示：
- 目前人數 / 累積不重複人數
- 人數趨勢圖
- 事件類型統計（近 24 小時）
- 即時標註畫面（含骨架與 ROI 標記）
- 事件紀錄表（可依嚴重度篩選）
- 「生成 AI Report」按鈕：彙整近期事件成一份摘要

### 3. （可選）啟用 Claude AI 摘要報告

預設在沒有金鑰時，AI Report 會使用內建的規則式模板摘要（離線可用）。
若想改用 Claude 生成更自然的中文摘要，設定環境變數即可：

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

並確認已安裝 `anthropic` SDK：`pip install anthropic`。

## 各事件類型說明

| event_type       | 說明                         | 預設嚴重度 |
|-------------------|------------------------------|-----------|
| `fall`            | 疑似跌倒（bbox 形狀 + 肩髖關鍵點判斷） | critical |
| `sudden_motion`   | 異常快速移動（追蹤點移動速度過快）      | warning  |
| `loitering`       | 同一人在同一 ROI 停留過久              | warning  |
| `roi_overcrowd`   | ROI 區域人數超過容量上限               | warning  |
| `global_overcrowd`| 畫面總人數超過閾值                     | warning  |
| `zone_enter`      | 進入 ROI 區域                          | info     |
| `zone_exit`       | 離開 ROI 區域                          | info     |

## 已知限制

- 跌倒/異常移動偵測為規則式（rule-based）輕量判斷，仰賴 bbox 形狀與少數關鍵點，
  在遮擋、多人重疊、鏡頭角度極端等情況下可能有誤判，正式場域建議搭配專門訓練過
  的行為辨識模型做二次確認。
- YouTube 直播的 CDN 網址有時效性，`stream_capture.py` 內建重連機制，但若直播
  本身已結束，仍會在重試數次後停止。
- ROI 多邊形座標是以「處理後的畫面像素座標」為準（即 `capture.resize_width`
  縮放後的座標），調整 `config.yaml` 的 zones 時請對應同一組座標系統。
