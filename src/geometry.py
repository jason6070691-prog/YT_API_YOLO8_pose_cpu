"""
geometry.py
共用的幾何工具函式（ROI 判斷、距離計算等），不依賴任何第三方套件，
方便在沒有安裝 shapely 的環境也能運作。
"""
from __future__ import annotations
from typing import List, Tuple

Point = Tuple[float, float]
Polygon = List[Point]


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """Ray-casting 演算法判斷點是否在多邊形內（含邊界近似）。"""
    x, y = point
    n = len(polygon)
    inside = False
    if n < 3:
        return False

    x1, y1 = polygon[0]
    for i in range(1, n + 1):
        x2, y2 = polygon[i % n]
        if y > min(y1, y2):
            if y <= max(y1, y2):
                if x <= max(x1, x2):
                    if y1 != y2:
                        x_intersect = (y - y1) * (x2 - x1) / (y2 - y1) + x1
                    else:
                        x_intersect = x1
                    if x1 == x2 or x <= x_intersect:
                        inside = not inside
        x1, y1 = x2, y2
    return inside


def euclidean_distance(p1: Point, p2: Point) -> float:
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


def bbox_center(xyxy) -> Point:
    x1, y1, x2, y2 = xyxy
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def bbox_foot_point(xyxy) -> Point:
    """以 bbox 底部中點近似人的『腳下位置』，較適合用來判斷 ROI 進出（貼地）。"""
    x1, y1, x2, y2 = xyxy
    return ((x1 + x2) / 2.0, y2)
