"""
pose_detector.py
對應 Workflow: YOLOv8-Pose → Person Detection → Pose Keypoints

負責載入 YOLOv8-Pose 模型，對每一幀進行推論，回傳結構化的 Detection 清單
(bbox + 信心值 + 17 個關鍵點)。同時使用 ultralytics 內建的 ByteTrack/BoT-SORT
指派 track_id，其結果會交給 tracker.py 做時序狀態維護。

COCO 17 個關鍵點順序:
0 鼻子 1 左眼 2 右眼 3 左耳 4 右耳 5 左肩 6 右肩 7 左肘 8 右肘
9 左腕 10 右腕 11 左髖 12 右髖 13 左膝 14 右膝 15 左踝 16 右踝
"""
from __future__ import annotations
import logging
from typing import List

import numpy as np
from ultralytics import YOLO

from .types import Detection
from .constants import SKELETON, LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP  # noqa: F401  (re-exported for backward-compat)

logger = logging.getLogger(__name__)


class PoseDetector:
    def __init__(
        self,
        weights: str = "yolov8n-pose.pt",
        device: str = "auto",
        conf_threshold: float = 0.3,
        iou_threshold: float = 0.5,
        tracker: str = "bytetrack.yaml",
    ):
        logger.info("載入 YOLOv8-Pose 模型: %s", weights)
        self.model = YOLO(weights)
        self.device = None if device == "auto" else device
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.tracker = tracker
        self._frame_idx = 0

    def infer(self, frame: np.ndarray, use_tracking: bool = True) -> List[Detection]:
        """對單一幀執行推論，回傳 Detection 清單。"""
        self._frame_idx += 1

        common_kwargs = dict(
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            verbose=False,
        )
        if self.device:
            common_kwargs["device"] = self.device

        if use_tracking:
            results = self.model.track(
                frame, persist=True, tracker=self.tracker, **common_kwargs
            )
        else:
            results = self.model.predict(frame, **common_kwargs)

        detections: List[Detection] = []
        if not results:
            return detections

        result = results[0]
        if result.boxes is None or result.keypoints is None:
            return detections

        boxes_xyxy = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        ids = (
            result.boxes.id.cpu().numpy().astype(int)
            if result.boxes.id is not None
            else [None] * len(boxes_xyxy)
        )
        kpts = result.keypoints.data.cpu().numpy()  # (N, 17, 3)

        for i in range(len(boxes_xyxy)):
            detections.append(
                Detection(
                    track_id=int(ids[i]) if ids[i] is not None else None,
                    bbox=tuple(float(v) for v in boxes_xyxy[i]),
                    conf=float(confs[i]),
                    keypoints=kpts[i].tolist(),
                    frame_idx=self._frame_idx,
                )
            )
        return detections

    def annotate(self, frame: np.ndarray, results=None) -> np.ndarray:
        """沿用 ultralytics 內建的 plot()，快速取得畫好骨架/框線的畫面（給 Dashboard 預覽用）。"""
        out = self.model.predict(frame, conf=self.conf_threshold, verbose=False)
        return out[0].plot() if out else frame
