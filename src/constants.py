"""
constants.py
COCO 17 個關鍵點的索引定義與骨架連線，獨立成檔避免其他純邏輯模組
(如 anomaly_detector.py) 被迫載入 ultralytics/torch 才能取得這些常數。
"""

# 0 鼻子 1 左眼 2 右眼 3 左耳 4 右耳 5 左肩 6 右肩 7 左肘 8 右肘
# 9 左腕 10 右腕 11 左髖 12 右髖 13 左膝 14 右膝 15 左踝 16 右踝
NOSE = 0
LEFT_EYE, RIGHT_EYE = 1, 2
LEFT_EAR, RIGHT_EAR = 3, 4
LEFT_SHOULDER, RIGHT_SHOULDER = 5, 6
LEFT_ELBOW, RIGHT_ELBOW = 7, 8
LEFT_WRIST, RIGHT_WRIST = 9, 10
LEFT_HIP, RIGHT_HIP = 11, 12
LEFT_KNEE, RIGHT_KNEE = 13, 14
LEFT_ANKLE, RIGHT_ANKLE = 15, 16

SKELETON = [
    (15, 13), (13, 11), (16, 14), (14, 12), (11, 12),
    (5, 11), (6, 12), (5, 6), (5, 7), (6, 8),
    (7, 9), (8, 10), (1, 2), (0, 1), (0, 2),
    (1, 3), (2, 4), (3, 5), (4, 6),
]
