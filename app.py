import os
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

from supabase import create_client


# ============================================================
# Streamlit 設定
# ============================================================

st.set_page_config(
    page_title="YOLOv8 即時監控 Dashboard",
    page_icon="🎥",
    layout="wide",
)


# ============================================================
# Supabase
# ============================================================

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL"
)

SUPABASE_KEY = (
    os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY"
    )
    or os.environ.get(
        "SUPABASE_KEY"
    )
)


if not SUPABASE_URL:

    st.error(
        "❌ 找不到 SUPABASE_URL"
    )

    st.stop()


if not SUPABASE_KEY:

    st.error(
        "❌ 找不到 "
        "SUPABASE_SERVICE_ROLE_KEY "
        "或 SUPABASE_KEY"
    )

    st.stop()


supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


# ============================================================
# 台灣時間
# ============================================================

TAIWAN_TZ = "Asia/Taipei"


def taiwan_time(value):

    if value is None:
        return "—"

    try:

        dt = pd.to_datetime(
            value,
            utc=True,
        )

        if pd.isna(dt):
            return "—"

        dt = dt.tz_convert(
            TAIWAN_TZ
        )

        return dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    except Exception:

        return str(value)


# ============================================================
# 取得最新 frame_stats
# ============================================================

def get_latest_frame_stats():

    try:

        response = (

            supabase

            .table(
                "frame_stats"
            )

            .select(
                "current_count, "
                "cumulative_unique_count, "
                "ts"
            )

            .order(
                "ts",
                desc=True,
            )

            .limit(1)

            .execute()
        )


        return (
            response.data[0]
            if response.data
            else None
        )


    except Exception as e:

        st.error(
            f"❌ frame_stats 讀取失敗：{e}"
        )

        return None


# ============================================================
# 取得人數趨勢
# ============================================================

def get_frame_stats():

    try:

        response = (

            supabase

            .table(
                "frame_stats"
            )

            .select(
                "current_count, "
                "cumulative_unique_count, "
                "ts"
            )

            .order(
                "ts",
                desc=True,
            )

            .limit(500)

            .execute()
        )


        rows = (
            response.data or []
        )


        # 最新 → 最舊
        # 改成最舊 → 最新
        rows.reverse()


        return rows


    except Exception as e:

        st.error(
            f"❌ frame_stats 趨勢讀取失敗：{e}"
        )

        return []


# ============================================================
# 取得事件
# ============================================================

def get_events():

    try:

        response = (

            supabase

            .table(
                "events"
            )

            .select(
                "event_type, "
                "severity, "
                "track_id, "
                "zone, "
                "timestamp"
            )

            .order(
                "timestamp",
                desc=True,
            )

            .limit(200)

            .execute()
        )


        return (
            response.data or []
        )


    except Exception as e:

        st.error(
            f"❌ events 讀取失敗：{e}"
        )

        return []


# ============================================================
# 標題
# ============================================================

st.title(
    "🎥 YOLOv8 即時監控 Dashboard"
)

st.caption(
    "YOLOv8-Pose ｜ "
    "即時人物偵測 ｜ "
    "行為 / 事件分析"
)


# ============================================================
# Dashboard 自動更新區
#
# Streamlit 每 2 秒重新執行這個 Fragment。
#
# 不再使用：
#
#     time.sleep(2)
#     st.rerun()
#
# ============================================================

@st.fragment(
    run_every=2
)
def dashboard():

    # ========================================================
    # 系統狀態
    # ========================================================

    col_status1, col_status2 = (
        st.columns([1, 5])
    )


    with col_status1:

        st.success(
            "🟢 系統運作中"
        )


    with col_status2:

        current_time = (
            datetime.now(
                timezone.utc
            )
            .astimezone(
                __import__(
                    "zoneinfo"
                ).ZoneInfo(
                    "Asia/Taipei"
                )
            )
        )


        st.caption(
            "最後 Dashboard 更新："
            + current_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )


    # ========================================================
    # 即時影像
    # ========================================================

    st.subheader(
        "🖼️ 即時監控畫面"
    )


    image_url = (

        f"{SUPABASE_URL}"

        "/storage/v1/object/public/"
        "frames/latest_frame.jpg"

        f"?t={int(datetime.now().timestamp())}"
    )


    st.image(
        image_url,
        use_container_width=True,
    )


    # ========================================================
    # 從 Supabase 取得資料
    # ========================================================

    latest = (
        get_latest_frame_stats()
    )

    frame_rows = (
        get_frame_stats()
    )

    events = (
        get_events()
    )


    # ========================================================
    # KPI
    # ========================================================

    current_count = (

        latest.get(
            "current_count",
            0,
        )

        if latest

        else 0
    )


    unique_count = (

        latest.get(
            "cumulative_unique_count",
            0,
        )

        if latest

        else 0
    )


    event_count = len(
        events
    )


    critical_count = sum(

        1

        for event in events

        if event.get(
            "severity"
        )
        == "critical"
    )


    st.subheader(
        "📊 即時統計"
    )


    col1, col2, col3, col4 = (
        st.columns(4)
    )


    with col1:

        st.metric(
            "目前人數",
            current_count,
        )


    with col2:

        st.metric(
            "累計不重複人數",
            unique_count,
        )


    with col3:

        st.metric(
            "事件總數",
            event_count,
        )


    with col4:

        st.metric(
            "重大事件",
            critical_count,
        )


    # ========================================================
    # 人數趨勢
    # ========================================================

    st.subheader(
        "📈 人數趨勢"
    )


    if frame_rows:

        df = pd.DataFrame(
            frame_rows
        )


        # ====================================================
        # 關鍵修正：
        #
        # Supabase TIMESTAMPTZ
        #       ↓
        # UTC
        #       ↓
        # Asia/Taipei
        #       ↓
        # 移除 timezone metadata
        #
        # 最後給 Plotly 的是「台灣當地時間」
        # ====================================================

        df["time"] = (
            pd.to_datetime(
                df["ts"],
                utc=True,
            )
            .dt
            .tz_convert(
                TAIWAN_TZ
            )
            .dt
            .tz_localize(None)
        )


        # ====================================================
        # 排序
        # ====================================================

        df = df.sort_values(
            "time"
        )


        # ====================================================
        # Plotly
        # ====================================================

        fig = px.line(

            df,

            x="time",

            y=[
                "current_count",
                "cumulative_unique_count",
            ],

            labels={

                "time": "台灣時間",

                "value": "人數",

                "variable": "統計項目",
            },

            title=(
                "即時人數變化"
            ),
        )


        fig.update_layout(

            hovermode=(
                "x unified"
            ),

            legend_title_text="",

            xaxis=dict(

                title="台灣時間",

                tickformat=(
                    "%m/%d %H:%M:%S"
                ),
            ),
        )


        st.plotly_chart(

            fig,

            use_container_width=True,

            key="people_trend",
        )


    else:

        st.info(
            "目前還沒有足夠的人數統計資料。"
        )


    # ========================================================
    # 事件統計
    # ========================================================

    st.subheader(
        "⚠️ 事件統計"
    )


    if events:

        event_df = pd.DataFrame(
            events
        )


        event_counts = (

            event_df[
                "event_type"
            ]

            .value_counts()

            .reset_index()
        )


        event_counts.columns = [
            "event_type",
            "count",
        ]


        fig = px.bar(

            event_counts,

            x="event_type",

            y="count",

            labels={

                "event_type": "事件類型",

                "count": "次數",
            },

            title="事件類型統計",
        )


        st.plotly_chart(

            fig,

            use_container_width=True,

            key="event_chart",
        )


    else:

        st.info(
            "目前尚未偵測到事件。"
        )


    # ========================================================
    # 最新事件
    # ========================================================

    st.subheader(
        "📋 最新事件"
    )


    if events:

        event_df = pd.DataFrame(
            events
        )


        event_df["時間"] = (

            event_df[
                "timestamp"
            ]

            .apply(
                taiwan_time
            )
        )


        event_df = (
            event_df.rename(
                columns={

                    "event_type":
                        "事件類型",

                    "severity":
                        "嚴重程度",

                    "track_id":
                        "人物 ID",
                }
            )
        )


        display_columns = [

            "時間",

            "事件類型",

            "嚴重程度",

            "人物 ID",
        ]


        display_columns = [

            column

            for column
            in display_columns

            if column
            in event_df.columns
        ]


        st.dataframe(

            event_df[
                display_columns
            ],

            use_container_width=True,

            hide_index=True,

            height=350,
        )


    else:

        st.success(
            "目前沒有事件紀錄 👍"
        )


    # ========================================================
    # Supabase 狀態
    # ========================================================

    st.divider()


    st.caption(
        "🔄 Dashboard 每 2 秒自動重新讀取 Supabase｜"
        "時間顯示為台灣時間（UTC+8）"
    )


# ============================================================
# 執行 Dashboard
# ============================================================

dashboard()
