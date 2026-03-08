"""
ESP32-CAM Pollution Monitor - Streamlit Dashboard
Run with: streamlit run dashboard.py
"""

import streamlit as st
import cv2
import numpy as np
import requests
import time
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from PIL import Image
import io
import threading
from detector import PollutionDetector
from config import CAMERAS, DB_PATH, REFRESH_INTERVAL

# ─── PAGE CONFIG ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ESP32 Pollution Monitor",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CUSTOM CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .main { background-color: #0a0f1a; }
  .stApp { background-color: #0a0f1a; color: #e0f0ff; }
  .metric-box {
    background: #111d2e;
    border: 1px solid rgba(0,200,255,0.2);
    border-radius: 8px;
    padding: 16px;
    text-align: center;
    margin-bottom: 12px;
  }
  .metric-label { font-size: 11px; letter-spacing: 2px; color: #5a8a9a; text-transform: uppercase; }
  .metric-value { font-size: 42px; font-weight: bold; line-height: 1.1; }
  .ok { color: #39ff14; }
  .warn { color: #ff6b35; }
  .danger { color: #ff2d55; }
  .cam-header { font-size: 11px; letter-spacing: 2px; color: #5a8a9a; text-transform: uppercase; margin-bottom: 4px; }
  .alert-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 11px;
    letter-spacing: 1px;
    font-weight: bold;
  }
  .badge-ok { background: rgba(57,255,20,0.15); color: #39ff14; border: 1px solid #39ff14; }
  .badge-warn { background: rgba(255,107,53,0.15); color: #ff6b35; border: 1px solid #ff6b35; }
  .badge-danger { background: rgba(255,45,85,0.15); color: #ff2d55; border: 1px solid #ff2d55; }
  .stButton > button {
    background: transparent;
    border: 1px solid rgba(0,200,255,0.4);
    color: #00e5ff;
    letter-spacing: 2px;
    font-size: 11px;
  }
  .stButton > button:hover { background: rgba(0,200,255,0.1); }
</style>
""", unsafe_allow_html=True)

# ─── INIT DB ─────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            camera_id TEXT,
            camera_name TEXT,
            haze_index REAL,
            smoke_detected INTEGER,
            water_polluted INTEGER,
            dust_level REAL,
            overall_status TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_reading(cam_id, cam_name, result):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO readings (timestamp, camera_id, camera_name, haze_index,
            smoke_detected, water_polluted, dust_level, overall_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        cam_id,
        cam_name,
        result.get("haze_index", 0),
        int(result.get("smoke_detected", False)),
        int(result.get("water_polluted", False)),
        result.get("dust_level", 0),
        result.get("overall_status", "UNKNOWN")
    ))
    conn.commit()
    conn.close()

def get_history(hours=6):
    conn = sqlite3.connect(DB_PATH)
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    df = pd.read_sql_query(
        "SELECT * FROM readings WHERE timestamp > ? ORDER BY timestamp ASC",
        conn, params=(since,)
    )
    conn.close()
    return df

# ─── FETCH + DETECT ──────────────────────────────────────────────────────────
@st.cache_resource
def get_detector():
    return PollutionDetector()

def fetch_and_analyze(cam):
    detector = get_detector()
    try:
        if cam.get("demo_mode", False):
            # Demo: generate synthetic image
            img = generate_demo_image(cam)
        else:
            url = f"http://{cam['ip']}/capture"
            resp = requests.get(url, timeout=5)
            arr = np.frombuffer(resp.content, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        if img is None:
            return None, None, {"error": "Failed to decode image"}

        result = detector.analyze(img, cam.get("roi"))
        annotated = detector.annotate(img.copy(), result)
        return img, annotated, result

    except requests.exceptions.ConnectionError:
        return None, None, {"error": f"Cannot connect to {cam.get('ip', 'camera')}"}
    except Exception as e:
        return None, None, {"error": str(e)}

def generate_demo_image(cam):
    """Generate realistic-looking synthetic pollution images for demo."""
    h, w = 480, 640
    img = np.zeros((h, w, 3), dtype=np.uint8)

    scenario = cam.get("demo_scenario", "clear")

    if scenario == "smoke":
        # Blue sky base
        img[:, :] = [180, 140, 80]
        # Add smoke region
        for i in range(h):
            for j in range(w//3, 2*w//3):
                dist = abs(i - h//2) / (h//2)
                smoke = int(180 * (1 - dist) * np.random.uniform(0.7, 1.0))
                img[i, j] = [smoke, smoke-20, smoke-30]
        img = cv2.GaussianBlur(img, (21, 21), 5)

    elif scenario == "haze":
        img[:, :] = [200, 200, 190]
        noise = np.random.randint(0, 30, (h, w, 3), dtype=np.uint8)
        img = cv2.add(img, noise)
        img = cv2.GaussianBlur(img, (15, 15), 8)

    elif scenario == "water":
        img[:h//2, :] = [120, 160, 200]  # sky
        # Polluted water
        for i in range(h//2, h):
            t = (i - h//2) / (h//2)
            color = [
                int(30 + 60*t),
                int(80 + 40*t),
                int(20 + 30*t)
            ]
            img[i, :] = color
        noise = np.random.randint(0, 20, (h, w, 3), dtype=np.uint8)
        img = cv2.add(img, noise)

    else:  # clear
        img[:h//2, :] = [200, 180, 140]  # sky
        img[h//2:, :] = [60, 100, 60]   # ground
        noise = np.random.randint(0, 15, (h, w, 3), dtype=np.uint8)
        img = cv2.add(img, noise)

    return img

# ─── STATUS BADGE HTML ───────────────────────────────────────────────────────
def badge(text, level):
    cls = {"ok": "badge-ok", "warn": "badge-warn", "danger": "badge-danger"}.get(level, "badge-warn")
    return f'<span class="alert-badge {cls}">{text}</span>'

def status_color(status):
    return {"CLEAN": "ok", "MODERATE": "warn", "POLLUTED": "danger"}.get(status, "warn")

# ─── MAIN APP ────────────────────────────────────────────────────────────────
def main():
    init_db()

    # ── SIDEBAR ──
    with st.sidebar:
        st.markdown("## 🌿 Pollution Monitor")
        st.markdown("---")
        st.markdown("**System Config**")
        refresh = st.slider("Refresh interval (s)", 5, 60, REFRESH_INTERVAL)
        show_raw = st.checkbox("Show raw image", False)
        show_annotated = st.checkbox("Show annotated image", True)
        st.markdown("---")
        st.markdown("**Thresholds**")
        haze_thresh = st.slider("Haze alert threshold", 20, 80, 50)
        dust_thresh = st.slider("Dust alert threshold", 10, 60, 30)
        st.markdown("---")
        st.markdown("**History**")
        history_hours = st.selectbox("Show last N hours", [1, 3, 6, 12, 24], index=2)
        st.markdown("---")
        auto_refresh = st.toggle("Auto Refresh", True)
        if st.button("🔄 Refresh Now"):
            st.rerun()

    # ── HEADER ──
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown("# 🌍 ESP32-CAM Pollution Monitor")
        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    with col_h2:
        active = sum(1 for c in CAMERAS if not c.get("disabled"))
        st.markdown(f"""
        <div class="metric-box">
          <div class="metric-label">Cameras Active</div>
          <div class="metric-value ok">{active} / {len(CAMERAS)}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── FETCH ALL CAMERAS ──
    all_results = []
    cam_images = []
    cam_annotated = []

    progress = st.progress(0, text="Fetching camera feeds...")
    for i, cam in enumerate(CAMERAS):
        if cam.get("disabled"):
            all_results.append(None)
            cam_images.append(None)
            cam_annotated.append(None)
        else:
            raw, annotated, result = fetch_and_analyze(cam)
            all_results.append(result)
            cam_images.append(raw)
            cam_annotated.append(annotated)
            if "error" not in result:
                save_reading(cam["id"], cam["name"], result)
        progress.progress((i + 1) / len(CAMERAS), text=f"Processed {cam['name']}...")

    progress.empty()

    # ── GLOBAL METRICS ──
    valid_results = [r for r in all_results if r and "error" not in r]
    if valid_results:
        avg_haze = np.mean([r["haze_index"] for r in valid_results])
        any_smoke = any(r["smoke_detected"] for r in valid_results)
        any_water = any(r["water_polluted"] for r in valid_results)
        avg_dust = np.mean([r["dust_level"] for r in valid_results])

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            haze_cls = "danger" if avg_haze > haze_thresh else ("warn" if avg_haze > haze_thresh * 0.7 else "ok")
            st.markdown(f"""<div class="metric-box">
              <div class="metric-label">Avg Haze Index</div>
              <div class="metric-value {haze_cls}">{avg_haze:.0f}%</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            smoke_cls = "danger" if any_smoke else "ok"
            smoke_txt = "DETECTED" if any_smoke else "CLEAR"
            st.markdown(f"""<div class="metric-box">
              <div class="metric-label">Smoke Status</div>
              <div class="metric-value {smoke_cls}">{smoke_txt}</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            water_cls = "danger" if any_water else "ok"
            water_txt = "POLLUTED" if any_water else "CLEAN"
            st.markdown(f"""<div class="metric-box">
              <div class="metric-label">Water Quality</div>
              <div class="metric-value {water_cls}">{water_txt}</div>
            </div>""", unsafe_allow_html=True)
        with m4:
            dust_cls = "danger" if avg_dust > dust_thresh else ("warn" if avg_dust > dust_thresh * 0.6 else "ok")
            st.markdown(f"""<div class="metric-box">
              <div class="metric-label">Dust Level</div>
              <div class="metric-value {dust_cls}">{avg_dust:.0f}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── CAMERA FEEDS ──
    st.markdown("### 📷 Camera Feeds")
    cols = st.columns(min(len(CAMERAS), 3))

    for i, (cam, result, raw, annotated) in enumerate(
        zip(CAMERAS, all_results, cam_images, cam_annotated)
    ):
        with cols[i % 3]:
            st.markdown(f'<div class="cam-header">{cam["name"]}</div>', unsafe_allow_html=True)

            if result and "error" not in result:
                status = result.get("overall_status", "UNKNOWN")
                sc = status_color(status)
                st.markdown(badge(status, sc), unsafe_allow_html=True)

                img_to_show = annotated if show_annotated and annotated is not None else raw
                if img_to_show is not None:
                    img_rgb = cv2.cvtColor(img_to_show, cv2.COLOR_BGR2RGB)
                    st.image(img_rgb, use_container_width=True)

                # Mini metrics
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("Haze", f"{result['haze_index']:.0f}%",
                              delta="HIGH" if result['haze_index'] > haze_thresh else None,
                              delta_color="inverse")
                with c2:
                    st.metric("Dust", f"{result['dust_level']:.0f}",
                              delta="HIGH" if result['dust_level'] > dust_thresh else None,
                              delta_color="inverse")

                smoke_b = badge("SMOKE", "danger") if result["smoke_detected"] else badge("NO SMOKE", "ok")
                water_b = badge("POLLUTED", "danger") if result["water_polluted"] else badge("CLEAN", "ok")
                st.markdown(f"{smoke_b} &nbsp; {water_b}", unsafe_allow_html=True)

            elif result and "error" in result:
                st.error(f"⚠ {result['error']}")
                st.info("Running in demo mode. Check camera connection.")
            else:
                st.warning("Camera disabled")

            st.markdown("<br>", unsafe_allow_html=True)

    # ── HISTORY CHART ──
    st.markdown("---")
    st.markdown("### 📈 Historical Trends")

    df = get_history(history_hours)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        tab1, tab2, tab3 = st.tabs(["Haze Index", "Smoke Events", "Dust Level"])

        with tab1:
            chart_data = df.pivot_table(
                index="timestamp", columns="camera_name", values="haze_index", aggfunc="mean"
            ).reset_index()
            st.line_chart(chart_data.set_index("timestamp"))

        with tab2:
            smoke_data = df.groupby(["timestamp", "camera_name"])["smoke_detected"].max().reset_index()
            smoke_pivot = smoke_data.pivot(index="timestamp", columns="camera_name", values="smoke_detected")
            st.area_chart(smoke_pivot)

        with tab3:
            dust_data = df.pivot_table(
                index="timestamp", columns="camera_name", values="dust_level", aggfunc="mean"
            ).reset_index()
            st.line_chart(dust_data.set_index("timestamp"))

        # Raw table
        with st.expander("📋 Raw Data Table"):
            st.dataframe(
                df[["timestamp", "camera_name", "haze_index", "smoke_detected",
                    "water_polluted", "dust_level", "overall_status"]].tail(50),
                use_container_width=True
            )
    else:
        st.info("No historical data yet. Data will appear after the first readings.")

    # ── AUTO REFRESH ──
    if auto_refresh:
        time.sleep(refresh)
        st.rerun()

if __name__ == "__main__":
    main()
