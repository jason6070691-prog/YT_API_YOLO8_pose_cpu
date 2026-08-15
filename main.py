#!/usr/bin/env python3
"""
main.py
專案進入點，完整串起 Workflow 的每一個節點:

YouTube Video/Live -> Stream Capture -> YOLOv8-Pose -> Person Detection
-> Pose Keypoints -> Person Tracking -> 行為/事件分析
   (人數統計 / 異常偵測 / ROI 區域) -> Event Engine -> Database/Log
-> (Streamlit Dashboard 讀取同一份 DB) -> Alert / AI Report

用法:
    python main.py                       # 使用 config.yaml 內的預設 YouTube 網址
    python main.py --url <youtube_url>   # 指定其他影片/直播網址
    python main.py --no-display          # 純後端模式，不開 cv2 視窗（伺服器/背景執行建議用這個）
"""
from __future__ import annotations
import argparse
import logging
import time
from pathlib import Path

import cv2

from src.config_loader import load_config
from src.stream_capture import StreamCapture
from src.pose_detector import PoseDetector
from src.tracker import PersonTracker
from src.behavior_analysis import BehaviorAnalyzer
from src.event_engine import EventEngine
from src.database import Database
from src.alert import AlertDispatcher
from supabase import create_client
import os

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"]
)

def upload_latest_frame():
    frame_path = Path("logs/latest_frame.jpg")

    if not frame_path.exists():
        return

    with open(frame_path, "rb") as f:
        try:
            supabase.storage.from_("frames").upload(
                path="latest_frame.jpg",
                file=f,
                file_options={
                    "cache-control": "3600",
                    "upsert": "true"
                }
            )
        except Exception:
            pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def draw_overlay(frame, fps: float, people_count: int, roi_snapshot: dict):
    overlay = frame.copy()
    panel_h = 90 + 22 * max(1, len(roi_snapshot))
    cv2.rectangle(overlay, (10, 10), (340, panel_h), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.65, frame, 0.35, 0)

    y = 35
    cv2.putText(frame, f"FPS: {fps:.1f}", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    y += 28
    cv2.putText(frame, f"People: {people_count}", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    y += 26
    for zone, cnt in roi_snapshot.items():
        cv2.putText(frame, f"{zone}: {cnt}", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
        y += 22
    return frame


def run(config_path: str = "config.yaml", url_override: str | None = None, show_window: bool = True):
    config = load_config(config_path)

    if url_override:
        config.source["youtube_url"] = url_override

    # ---- 1~2. Stream Capture ----
    capture = StreamCapture(
        youtube_url=config.source.youtube_url,
        preferred_max_height=config.source.preferred_max_height,
        buffer_size=config.capture.buffer_size,
        frame_skip=config.capture.frame_skip,
        resize_width=config.capture.resize_width,
        reconnect_retries=config.source.reconnect_retries,
        reconnect_delay_sec=config.source.reconnect_delay_sec,
    )

    # ---- 3~5. YOLOv8-Pose / Person Detection / Pose Keypoints ----
    detector = PoseDetector(
        weights=config.model.weights,
        device=config.model.device,
        conf_threshold=config.model.conf_threshold,
        iou_threshold=config.model.iou_threshold,
        tracker=config.tracking.tracker,
    )

    # ---- 6. Person Tracking ----
    tracker = PersonTracker(
        max_history=config.tracking.max_history,
        lost_track_ttl_sec=config.tracking.lost_track_ttl_sec,
    )

    # ---- 7. 行為/事件分析 (人數統計 / 異常偵測 / ROI 區域) ----
    analyzer = BehaviorAnalyzer(config, tracker)

    # ---- 8. Event Engine + Database + Alert ----
    database = Database(path=config.database.path)
    alert_dispatcher = AlertDispatcher(
        console=config.alert.console,
        webhook_url=config.alert.webhook_url,
        min_severity=config.alert.min_severity,
    )
    event_engine = EventEngine(
        database=database,
        alert_dispatcher=alert_dispatcher,
        severity_map=dict(config.event_engine.severity_map),
        dedupe_window_sec=config.event_engine.dedupe_window_sec,
    )

    window_name = "YouTube 姿態辨識 / 行為事件分析 (YOLOv8-Pose)"
    if show_window:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)

    frame_count, fps, t0 = 0, 0.0, time.time()
    last_frame_save = 0.0
    annotated_path = Path(config.capture.annotated_frame_path)
    annotated_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("啟動 YOLOv8-Pose 行為/事件分析 Pipeline")
    logger.info("目標串流: %s", config.source.youtube_url)
    logger.info("=" * 60)

    try:
        for frame in capture.iterate_frames():
            frame_count += 1
            elapsed = time.time() - t0
            if elapsed >= 1:
                fps = frame_count / elapsed
                frame_count, t0 = 0, time.time()

            # 3~6. 偵測 + 關鍵點 + 追蹤 ID
            detections = detector.infer(frame, use_tracking=True)
            tracks = tracker.update(detections)

            # 7. 行為/事件分析
            people_stats, raw_events = analyzer.analyze(detections, tracks)

            # 8. Event Engine -> Database -> Alert
            event_engine.process(raw_events)
            if people_stats and people_stats.get("should_log"):
                database.insert_frame_stats(
                    current_count=people_stats["current_count"],
                    cumulative_unique_count=people_stats["cumulative_unique_count"],
                )

            # 畫面標註（沿用 ultralytics 內建骨架繪製 + 自訂資訊面板）
            roi_snapshot = analyzer.roi_snapshot(tracks)
            people_count = people_stats["current_count"] if people_stats else tracker.active_count()
            annotated = detector.model.predict(frame, conf=config.model.conf_threshold, verbose=False)[0].plot()
            annotated = draw_overlay(annotated, fps, people_count, roi_snapshot)

            now = time.time()
            if config.capture.save_annotated_frame and (
                now - last_frame_save >= config.capture.annotated_frame_interval_sec
            ):
                cv2.imwrite(str(annotated_path), annotated)
                upload_latest_frame()
                last_frame_save = now

            if show_window:
                cv2.imshow(window_name, annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    logger.info("使用者中止")
                    break

    except KeyboardInterrupt:
        logger.info("程式被中斷")
    finally:
        capture.release()
        if show_window:
            cv2.destroyAllWindows()
        database.close()
        logger.info("Pipeline 已停止")


def parse_args():
    parser = argparse.ArgumentParser(description="YouTube YOLOv8-Pose 行為/事件分析 Pipeline")
    parser.add_argument("--config", default="config.yaml", help="設定檔路徑")
    parser.add_argument("--url", default=None, help="覆寫 config.yaml 內的 YouTube 網址")
    parser.add_argument("--no-display", action="store_true", help="不開啟 cv2 視窗（背景/伺服器模式）")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(config_path=args.config, url_override=args.url, show_window=not args.no_display)
