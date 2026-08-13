"""
stream_capture.py
對應 Workflow: YouTube Video / Live → Stream Capture

負責:
  1. 用 yt-dlp 解析 YouTube 影片/直播，取得可被 OpenCV 讀取的串流 URL
  2. 包裝 cv2.VideoCapture，提供一個穩定的 frame generator
  3. 串流中斷時自動重連（直播常見）
"""
from __future__ import annotations
import time
import logging
from typing import Iterator, Optional

import cv2
import yt_dlp
import numpy as np

logger = logging.getLogger(__name__)


def extract_stream_url(youtube_url: str, preferred_max_height: int = 720) -> Optional[str]:
    """解析 YouTube 網址，回傳可直接被 cv2.VideoCapture 開啟的直連 URL。"""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "nocheckcertificate": True,
        "geo_bypass": True,
    }
    try:
        logger.info("正在解析 YouTube 串流 URL...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)

            formats = info.get("formats") or []
            video_formats = [f for f in formats if f.get("vcodec") != "none" and f.get("url")]

            if video_formats:
                video_formats.sort(key=lambda f: f.get("height") or 0, reverse=True)
                for fmt in video_formats:
                    h = fmt.get("height") or 0
                    if 0 < h <= preferred_max_height:
                        logger.info("已選擇畫質: %sp", h)
                        return fmt["url"]
                best = video_formats[0]
                logger.info("找不到 <=%sp 的格式，改用最佳格式: %sp",
                            preferred_max_height, best.get("height", "unknown"))
                return best["url"]

            if info.get("url"):
                return info["url"]

        raise RuntimeError("找不到合適的影片格式")
    except Exception as exc:  # noqa: BLE001
        logger.error("提取串流 URL 失敗: %s", exc)
        return None


class StreamCapture:
    """包裝 cv2.VideoCapture，對外提供 iterate_frames()。"""

    def __init__(
        self,
        youtube_url: str,
        preferred_max_height: int = 720,
        buffer_size: int = 1,
        frame_skip: int = 2,
        resize_width: Optional[int] = None,
        reconnect_retries: int = 5,
        reconnect_delay_sec: float = 3.0,
    ):
        self.youtube_url = youtube_url
        self.preferred_max_height = preferred_max_height
        self.buffer_size = buffer_size
        self.frame_skip = max(1, frame_skip)
        self.resize_width = resize_width
        self.reconnect_retries = reconnect_retries
        self.reconnect_delay_sec = reconnect_delay_sec

        self.cap: Optional[cv2.VideoCapture] = None
        self.width = 0
        self.height = 0

    # -- 內部: 開啟串流 --
    def _open(self) -> bool:
        stream_url = extract_stream_url(self.youtube_url, self.preferred_max_height)
        if not stream_url:
            return False

        cap = cv2.VideoCapture(stream_url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
        if not cap.isOpened():
            logger.error("cv2.VideoCapture 無法開啟串流")
            return False

        self.cap = cap
        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info("串流已開啟: %sx%s", self.width, self.height)
        return True

    def _reconnect(self) -> bool:
        for attempt in range(1, self.reconnect_retries + 1):
            logger.warning("嘗試重新連線 (%s/%s)...", attempt, self.reconnect_retries)
            if self.cap is not None:
                self.cap.release()
            time.sleep(self.reconnect_delay_sec)
            if self._open():
                return True
        return False

    def _resize(self, frame: np.ndarray) -> np.ndarray:
        if not self.resize_width:
            return frame
        h, w = frame.shape[:2]
        if w == self.resize_width:
            return frame
        scale = self.resize_width / float(w)
        return cv2.resize(frame, (self.resize_width, int(h * scale)))

    def iterate_frames(self) -> Iterator[np.ndarray]:
        """持續產生影格；串流中斷時會嘗試自動重連，重連失敗才結束。"""
        if self.cap is None and not self._open():
            raise RuntimeError("無法開啟初始串流")

        frame_idx = 0
        while True:
            ret, frame = self.cap.read()
            if not ret:
                logger.warning("讀取影格失敗，可能是串流中斷")
                if not self._reconnect():
                    logger.error("重連失敗，結束串流讀取")
                    break
                continue

            frame_idx += 1
            if frame_idx % self.frame_skip != 0:
                continue

            yield self._resize(frame)

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
