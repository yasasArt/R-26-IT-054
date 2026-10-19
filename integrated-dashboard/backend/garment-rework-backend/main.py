import cv2
import time
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pydantic import BaseModel
import supervision as sv
from ultralytics import YOLO
import uvicorn
import sqlite3
import os
from pathlib import Path

BACKEND_DIRECTORY = Path(__file__).resolve().parent
DATA_DIRECTORY = Path(os.environ.get("GARMENT_REWORK_DATA_DIR", BACKEND_DIRECTORY / "data")).expanduser().resolve()
DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = DATA_DIRECTORY / "garment_data.db"
MODEL_PATH = Path(os.environ.get("GARMENT_REWORK_MODEL_PATH", BACKEND_DIRECTORY / "best.pt")).expanduser().resolve()

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    # session_id තීරුව අලුතින් එක් කර ඇත
    c.execute('''
        CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            tracker_id INTEGER,
            verdict TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()
# ----------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AppState:
    def __init__(self):
        self.running = False
        self.cap = None
        self.current_session_id = None # අලුත් Session ID එක රඳවා ගැනීමට
        
        self.good_count = 0
        self.rework_count = 0
        self.event_log = []
        self.history = []
        self.frame_idx = 0
        
        self.conf_threshold = 0.25
        self.top_pct = 30
        self.bottom_pct = 70
        self.center_min_pct = 10
        self.center_max_pct = 90

        # Video-file playback speed (1x, 2x, 3x). Frames are processed as fast
        # as the model allows, so a higher speed inspects every 2nd / 3rd
        # frame of the file. Live webcams always use 1x.
        self.playback_speed = 1
        self.source_is_file = False
        
        self.model = None
        self.byte_tracker = None
        self.track_states = {}

state = AppState()

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "feature": "garment-rework-counter",
        "model_path": str(MODEL_PATH),
        "database_path": str(DATABASE_PATH),
    }

MAX_PLAYBACK_SPEED = 3

def clamp_speed(value):
    try:
        return max(1, min(MAX_PLAYBACK_SPEED, int(value)))
    except (TypeError, ValueError):
        return 1

class StartRequest(BaseModel):
    source_type: str
    source_val: str
    conf_threshold: float
    top_pct: int
    bottom_pct: int
    center_min_pct: int
    center_max_pct: int
    playback_speed: int = 1

class UpdateRequest(BaseModel):
    conf_threshold: float
    top_pct: int
    bottom_pct: int
    center_min_pct: int
    center_max_pct: int
    playback_speed: Optional[int] = None

@app.post("/start")
def start_inspection(req: StartRequest):
    try:
        if state.running:
            return {"status": "already running"}
            
        state.model = YOLO(str(MODEL_PATH))
        
        source = int(req.source_val) if req.source_val.isdigit() else req.source_val
        state.cap = cv2.VideoCapture(source)
        
        if not state.cap.isOpened():
            return {"status": "error", "message": "Could not open video source"}
            
        state.byte_tracker = sv.ByteTrack(track_activation_threshold=0.20, lost_track_buffer=120)
        state.track_states = {}
        state.good_count = 0
        state.rework_count = 0
        state.event_log = []
        state.history = []
        state.frame_idx = 0
        
        # අලුත් Session එකක් ආරම්භ කිරීම (උදා: SESSION_20260827_231020)
        state.current_session_id = f"SESSION_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        state.conf_threshold = req.conf_threshold
        state.top_pct = req.top_pct
        state.bottom_pct = req.bottom_pct
        state.center_min_pct = req.center_min_pct
        state.center_max_pct = req.center_max_pct
        state.source_is_file = not isinstance(source, int)
        state.playback_speed = clamp_speed(req.playback_speed) if state.source_is_file else 1
        
        state.running = True
        return {"status": "started", "session_id": state.current_session_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/update_settings")
def update_settings(req: UpdateRequest):
    state.conf_threshold = req.conf_threshold
    state.top_pct = req.top_pct
    state.bottom_pct = req.bottom_pct
    state.center_min_pct = req.center_min_pct
    state.center_max_pct = req.center_max_pct
    if req.playback_speed is not None and state.source_is_file:
        state.playback_speed = clamp_speed(req.playback_speed)
    return {"status": "updated", "playback_speed": state.playback_speed}

@app.post("/stop")
def stop_inspection():
    state.running = False
    if state.cap:
        state.cap.release()
        state.cap = None
    return {"status": "stopped"}

@app.get("/metrics")
def get_metrics():
    # Session එකක් පටන් අරන් නැත්නම් බිංදුව පෙන්වන්න
    if not state.current_session_id:
        return {"good": 0, "rework": 0, "history": [], "log": []}

    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    
    # දැනට දුවන Session එකේ දත්ත පමණක් ලබා ගැනීම
    c.execute("SELECT COUNT(*) FROM inspections WHERE verdict='Good' AND session_id=?", (state.current_session_id,))
    good_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM inspections WHERE verdict='Rework' AND session_id=?", (state.current_session_id,))
    rework_count = c.fetchone()[0]
    
    c.execute("SELECT tracker_id, verdict, timestamp FROM inspections WHERE session_id=? ORDER BY id DESC LIMIT 50", (state.current_session_id,))
    rows = c.fetchall()
    
    log = [{"id": row[0], "verdict": row[1], "timestamp": row[2]} for row in rows]
    conn.close()
    
    return {
        "good": good_count,
        "rework": rework_count,
        "history": state.history[-100:] if state.history else [],
        "log": log
    }

def log_verdict(tid, verdict):
    current_time = datetime.now().strftime("%H:%M:%S")
    
    if verdict == "Good":
        state.good_count += 1
    else:
        state.rework_count += 1
        
    # අදාළ Session එක යටතේ Database එකට සුරැකීම
    if state.current_session_id:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO inspections (session_id, tracker_id, verdict, timestamp) VALUES (?, ?, ?, ?)", 
                  (state.current_session_id, int(tid), verdict, current_time))
        conn.commit()
        conn.close()

def generate_frames():
    box_annotator = sv.BoxAnnotator(thickness=2)
    label_annotator = sv.LabelAnnotator(text_scale=0.5)

    while state.running and state.cap and state.cap.isOpened():
        ret, frame = state.cap.read()
        if not ret:
            state.running = False
            break

        # 2x / 3x playback for video files: skip the next 1 or 2 frames
        # (grab() advances without decoding them for display).
        skipped = 0
        if state.source_is_file and state.playback_speed > 1:
            for _ in range(state.playback_speed - 1):
                if not state.cap.grab():
                    break
                skipped += 1

        height, width = frame.shape[:2]
        top_y = int(height * state.top_pct / 100)
        bottom_y = int(height * state.bottom_pct / 100)
        center_x_min = int(width * state.center_min_pct / 100)
        center_x_max = int(width * state.center_max_pct / 100)

        results = state.model(frame, conf=state.conf_threshold, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(results)
        detections = state.byte_tracker.update_with_detections(detections)

        current_ids = []
        if detections.tracker_id is not None and len(detections) > 0:
            current_ids = detections.tracker_id.tolist()

        for i, tracker_id in enumerate(current_ids):
            x1, y1, x2, y2 = detections.xyxy[i]
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0

            current_zone = "MID"
            if cy < top_y:
                current_zone = "UP"
            elif cy > bottom_y:
                current_zone = "DOWN"

            in_center_roi = center_x_min <= cx <= center_x_max
            if not in_center_roi:
                current_zone = "MID"

            if tracker_id not in state.track_states:
                state.track_states[tracker_id] = {
                    "zone": "MID", "has_visited_mid": False,
                    "counted": False, "missing_frames": 0,
                }

            t_state = state.track_states[tracker_id]
            t_state["missing_frames"] = 0

            if current_zone == "MID" and in_center_roi:
                t_state["has_visited_mid"] = True

            t_state["zone"] = current_zone

            if not t_state["counted"] and t_state["has_visited_mid"] and current_zone in ("UP", "DOWN"):
                t_state["counted"] = True
                log_verdict(tracker_id, "Good" if current_zone == "UP" else "Rework")

        for tid, t_state in state.track_states.items():
            if tid not in current_ids and not t_state["counted"] and t_state["has_visited_mid"]:
                t_state["missing_frames"] += 1
                if t_state["missing_frames"] == 3 and t_state["zone"] in ("UP", "DOWN"):
                    t_state["counted"] = True
                    log_verdict(tid, "Good" if t_state["zone"] == "UP" else "Rework")

        labels = [f"ID:{tid}" for tid in detections.tracker_id] if detections.tracker_id is not None else []
        annotated_frame = box_annotator.annotate(scene=frame.copy(), detections=detections)
        if labels:
            annotated_frame = label_annotator.annotate(scene=annotated_frame, detections=detections, labels=labels)

        cv2.line(annotated_frame, (0, top_y), (width, top_y), (113, 204, 46), 2)  
        cv2.line(annotated_frame, (0, bottom_y), (width, bottom_y), (60, 76, 231), 2) 
        cv2.line(annotated_frame, (center_x_min, top_y), (center_x_min, bottom_y), (15, 196, 241), 2)
        cv2.line(annotated_frame, (center_x_max, top_y), (center_x_max, bottom_y), (15, 196, 241), 2)

        state.frame_idx += 1 + skipped
        
        # Chart එකට දත්ත ලබා දීම (DB එක Load කරන්නේ නැතිව කෙලින්ම State එකෙන් දෙන නිසා ලැග් වෙන්නේ නෑ)
        state.history.append({
            "frame": state.frame_idx,
            "good": state.good_count,
            "rework": state.rework_count,
        })
        if len(state.history) > 500:
            state.history = state.history[-500:]

        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.get("/video_feed")
def video_feed():
    if not state.running:
        return {"status": "not running"}
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/sessions")
def get_all_sessions():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    
    # හැම Session එකක්ම Group කරලා Good/Rework වෙන වෙනම ගණන් කරනවා
    c.execute('''
        SELECT 
            session_id,
            SUM(CASE WHEN verdict='Good' THEN 1 ELSE 0 END) as good_count,
            SUM(CASE WHEN verdict='Rework' THEN 1 ELSE 0 END) as rework_count,
            MIN(timestamp) as start_time,
            MAX(timestamp) as end_time
        FROM inspections 
        WHERE session_id IS NOT NULL
        GROUP BY session_id 
        ORDER BY MAX(id) DESC
    ''')
    rows = c.fetchall()
    conn.close()
    
    sessions_history = []
    for row in rows:
        good = row[1] or 0
        rework = row[2] or 0
        sessions_history.append({
            "session_id": row[0],
            "good": good,
            "rework": rework,
            "total": good + rework,
            "pass_rate": round((good / (good + rework) * 100), 1) if (good + rework) > 0 else 0.0,
            "start_time": row[3],
            "end_time": row[4]
        })
        
    return sessions_history

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("GARMENT_FEATURE_PORT", "8011")))
