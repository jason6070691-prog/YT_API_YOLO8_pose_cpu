from **future** import annotations

import os
import time
import streamlit as st

# ----------------------------

# Streamlit 基本設定

# ----------------------------

st.set_page_config(
page_title="YOLOv8-Pose 即時監控 Dashboard",
layout="wide"
)

# ----------------------------

# Supabase Storage 圖片網址

# ----------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL")

if not SUPABASE_URL:
st.error("環境變數 SUPABASE_URL 尚未設定，請到 Render -> Environment 新增。")
st.stop()

IMAGE_URL = f"{SUPABASE_URL}/storage/v1/object/public/frames/latest_frame.jpg"

# ----------------------------

# 標題

# ----------------------------

st.title("🎥 YOLOv8-Pose 即時監控 Dashboard")
st.caption("本機 main.py 正在分析 YouTube 直播，畫面同步到 Supabase Storage。")

# ----------------------------

# 側邊欄

# ----------------------------

auto_refresh = st.sidebar.checkbox("自動刷新", value=True)
refresh_sec = st.sidebar.slider("刷新間隔（秒）", 1, 10, 3)

if st.sidebar.button("立即刷新"):
st.rerun()

# ----------------------------

# 主畫面

# ----------------------------

st.subheader("🖼️ 即時畫面（YOLOv8 Pose 標註）")

# 用 timestamp 避免瀏覽器快取

image_url = f"{IMAGE_URL}?t={int(time.time())}"

st.image(image_url, use_container_width=True)

st.success("若本機 main.py 正在執行，畫面會每隔幾秒自動更新。")

# ----------------------------

# 自動刷新

# ----------------------------

if auto_refresh:
time.sleep(refresh_sec)
st.rerun()
