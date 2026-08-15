from future import annotations

import os
import time
import streamlit as st

st.set_page_config(page_title="YOLOv8 Dashboard", layout="wide")

SUPABASE_URL = os.environ.get("SUPABASE_URL")

if not SUPABASE_URL:
  st.error("請在 Render 設定 SUPABASE_URL 環境變數")
  st.stop()

st.title("🎥 YOLOv8 即時監控 Dashboard")

image_url = (
f"{SUPABASE_URL}/storage/v1/object/public/frames/latest_frame.jpg?t={int(time.time())}"
)

st.image(image_url, use_container_width=True)

st.success("如果本機 main.py 正在執行，畫面會自動更新。")
