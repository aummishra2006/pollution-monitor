# 🌿 ESP32-CAM Pollution Monitor

A real-time environmental pollution detection system using ESP32-CAM cameras and Python/Streamlit.

## 📁 File Structure

```
pollution_monitor/
├── dashboard.py        ← Streamlit dashboard (main entry point)
├── detector.py         ← OpenCV detection engine
├── config.py           ← Camera IPs and settings
├── esp32_sketch.ino    ← Arduino sketch for ESP32-CAM
├── requirements.txt    ← Python dependencies
└── README.md
```

## 🚀 Quick Start (Demo Mode — No Hardware Needed)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the dashboard (cameras default to demo mode)
streamlit run dashboard.py
```

Open http://localhost:8501 in your browser.

## 🔧 Real Hardware Setup

### Step 1: Flash ESP32-CAM
1. Open `esp32_sketch.ino` in Arduino IDE
2. Set your WiFi credentials in the sketch
3. Connect ESP32-CAM via FTDI adapter
4. Hold GPIO0 to GND during upload
5. Open Serial Monitor at 115200 baud
6. Note the IP address printed on boot

### Step 2: Configure Cameras
Edit `config.py`:
```python
CAMERAS = [
    {
        "id": "cam_01",
        "name": "Factory North",
        "ip": "192.168.1.101",   # ← Your ESP32 IP here
        "demo_mode": False,       # ← Set to False for real hardware
        "roi": None,
    },
]
```

### Step 3: Launch Dashboard
```bash
streamlit run dashboard.py
```

## 🔍 What Gets Detected

| Type | Method | Threshold |
|------|--------|-----------|
| Haze/Smog | Dark Channel Prior + Contrast | Haze index > 50% |
| Smoke Plumes | HSV masking (grey-black range) | Coverage > 20% of frame |
| Water Pollution | HSV color analysis (brown/green) | Coverage > 25% of ROI |
| Dust Level | Laplacian blur variance | Dust score > 50 |

## 📊 Dashboard Features

- **Live camera feeds** from all ESP32-CAMs
- **Annotated images** with detection overlays
- **Global metrics** — haze, smoke status, water quality, dust
- **Historical trends** — line charts over configurable time windows
- **SQLite logging** — all readings persisted automatically
- **Auto-refresh** — configurable interval (5–60 seconds)

## ⚙️ Adding More Cameras

Add entries to the `CAMERAS` list in `config.py`. Each ESP32-CAM needs:
- A static IP (set via router DHCP reservation using the ESP32 MAC address)
- The Arduino sketch flashed onto it

## 📧 Optional Alerts

Enable email or SMS alerts in `config.py`:
```python
EMAIL_ALERTS = True
EMAIL_SENDER = "your@gmail.com"
EMAIL_PASSWORD = "your_app_password"   # Gmail App Password
EMAIL_RECIPIENT = "alerts@email.com"
```

## 🧠 Upgrading Detection

For higher accuracy, replace the OpenCV smoke detector with YOLOv8:
```bash
pip install ultralytics
```
Then in `detector.py`, load a pretrained model:
```python
from ultralytics import YOLO
model = YOLO("yolov8n.pt")
results = model(img)
```
Datasets for fine-tuning are available on Roboflow (search "smoke detection").
