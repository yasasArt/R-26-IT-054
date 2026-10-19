import cv2
import numpy as np
import requests
import sys
import platform
import os
import base64
import threading
import time
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from ultralytics import YOLO
from pathlib import Path

from style_engine import EngineConfig, StyleCaptureEngine, YoloStyleClassifier

# pygrabber wraps DirectShow, which only exists on Windows - camera
# enumeration/opening below branches on IS_WINDOWS and uses a generic
# OpenCV-only path everywhere else (see list_cameras() and switch_camera()).
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    from pygrabber.dshow_graph import FilterGraph
    import comtypes

# --- CONFIGURATION ---
STYLE_MODEL_PATH = Path(os.environ.get("THREADSCAN_MODEL_PATH", Path(__file__).resolve().parent / "best.pt"))

# Version 3.2: the per-frame "first two sharp frames >= 85 %" capture rule
# (and its 90-frame auto-unlock) was replaced by StyleCaptureEngine - see
# style_engine.py for the measured reasons. In short, the model is only asked
# about a tight crop of a garment that is really on the table (found by
# comparing with a learned picture of the empty folding zone), only once the
# garment has settled and no hand/face covers it, and several frames must
# agree. After a capture the zone stays locked until the garment is removed,
# so folding never creates a second (wrong) record.
#
# The crop is classified at the model's training size (640). On a CPU-only
# machine this costs ~50 ms, but it only runs while a settled garment is being
# analysed (a few frames per garment), not on every camera frame.
CLASSIFY_IMGSZ = int(os.environ.get("THREADSCAN_CLASSIFY_IMGSZ", "640"))
BACKEND_API_BASE = os.environ.get("THREADSCAN_BACKEND_API_BASE", "http://127.0.0.1:8000").rstrip("/")


print("Loading YOLO AI Model... Please wait.")

try:
    yolo_model = YOLO(str(STYLE_MODEL_PATH))
    print("✅ YOLO Style Model loaded successfully!")
except Exception as e:
    print(f"❌ Error loading YOLO model: {e}")
    sys.exit(1)

style_classifier = YoloStyleClassifier(yolo_model, imgsz=CLASSIFY_IMGSZ)
style_engine = StyleCaptureEngine(style_classifier, style_classifier.class_names, EngineConfig.from_env())

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": [r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$", "garment://app"]}})

global_frame = None
lock = threading.Lock()

def generate_frames():
    global global_frame
    while True:
        with lock:
            if global_frame is None:
                frame_to_send = None
            else:
                ret, buffer = cv2.imencode('.jpg', global_frame)
                frame_to_send = buffer if ret else None

        if frame_to_send is None:
            # No frame yet (camera still starting up, or not connected) -
            # wait briefly instead of busy-spinning. Without this, an idle
            # /video_feed viewer pins the single request-handling thread at
            # 100% CPU forever, which - combined with Flask's dev server
            # being single-threaded by default - blocks every other request
            # the app needs to serve (garment posts, the Demo upload, etc.).
            time.sleep(0.05)
            continue

        frame_bytes = frame_to_send.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def _skin_mask(bgr_image):
    """Rough skin-tone mask in YCrCb space (the standard Chai & Ngan range).
    A hand resting on or near the garment is the one intrusion GrabCut's
    colour model most often gets wrong on its own - skin tone and some
    fabric colours (beige, tan) can land in the same Gaussian mixture
    component - so it is subtracted from the foreground mask explicitly
    rather than left for GrabCut to figure out unaided."""
    ycrcb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2YCrCb)
    lower = np.array([0, 133, 77], dtype=np.uint8)
    upper = np.array([255, 173, 127], dtype=np.uint8)
    return cv2.inRange(ycrcb, lower, upper) > 0

def _clean_mask(fg_mask):
    """Morphological cleanup on the raw GrabCut+skin-mask output. An opening
    pass shaves off thin protrusions - fingers gripping the fabric, a wisp
    of hair - that are directly connected to the main garment blob without
    eating into its bulk, the way a plain rectangle-of-pixels mask can't.
    Keeping only the largest surviving connected component then drops any
    separate island GrabCut still called 'foreground' elsewhere in the crop
    (a corner of table, a hand not touching the garment) so it can't drag
    the tight-crop bounding box back out or leak into the colour sample."""
    h, w = fg_mask.shape
    kernel_size = max(3, int(round(min(h, w) * 0.035))) | 1  # odd, scales with crop size
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))

    opened = cv2.morphologyEx(fg_mask.astype(np.uint8), cv2.MORPH_OPEN, kernel)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    if num_labels <= 1:
        return fg_mask  # opening wiped everything out - let the caller's size fallback handle it

    largest_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return labels == largest_label

def _garment_foreground_mask(bgr_image):
    """GrabCut foreground mask, seeded with an explicit border/core prior
    instead of a bare rectangle: a wide outer ring is marked 'probably
    background', a large centre region 'definitely foreground' (a garment
    that was already detected and area-checked by YOLO fills most of its
    own crop, so a generous positive seed gives GrabCut's colour model a
    much better sample of the true garment colour to work from), and a
    narrow band between the two is left for GrabCut to decide. A plain
    rect-only init treats the whole crop as equally likely to be
    foreground, which is why a hand or hair entering from the crop edge -
    or a sliver of table at a corner - used to survive into the
    'foreground' region. Skin-toned pixels are then explicitly removed on
    top of that, and the result is morphologically cleaned to drop thin
    protrusions and stray islands. Falls back to 'everything is
    foreground' if GrabCut fails or the mask collapses to almost nothing."""
    h, w = bgr_image.shape[:2]
    mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)

    border = max(2, int(min(h, w) * 0.10))
    mask[border:h - border, border:w - border] = cv2.GC_PR_FGD

    core_y, core_x = int(h * 0.18), int(w * 0.18)
    if h - 2 * core_y > 0 and w - 2 * core_x > 0:
        mask[core_y:h - core_y, core_x:w - core_x] = cv2.GC_FGD

    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(bgr_image, mask, (0, 0, w, h), bgd_model, fgd_model, 8, cv2.GC_INIT_WITH_MASK)
        fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), True, False)
    except cv2.error:
        fg_mask = np.ones((h, w), dtype=bool)

    fg_mask &= ~_skin_mask(bgr_image)
    fg_mask = _clean_mask(fg_mask)

    if fg_mask.sum() < (h * w) * 0.05:
        # Segmentation collapsed - e.g. skin removal ate a skin-toned
        # garment, or GrabCut found nothing it was confident about. Fall
        # back to "everything is foreground" rather than clustering on a
        # near-empty pixel set.
        fg_mask = np.ones((h, w), dtype=bool)

    return fg_mask

def _inset_crop(image, margin=0.08):
    """Trims a margin off each side before segmentation. A detector's box
    edges are exactly where localization is least precise, so this biases
    the crop toward the garment's core - defense in depth on top of the
    GrabCut foreground mask below, not a replacement for it."""
    h, w = image.shape[:2]
    dy, dx = int(h * margin), int(w * margin)
    if h - 2 * dy < 10 or w - 2 * dx < 10:
        return image  # crop too small to inset further
    return image[dy:h - dy, dx:w - dx]

def segment_garment(image_crop, margin=0.08, max_dim=320):
    """Internal-only helper for colour extraction - NOT for anything shown
    to the operator. Returns a working copy of the garment region plus the
    foreground mask that excludes background/hand/hair pixels from it, so
    extract_colors_from_segment can sample only genuine garment pixels.
    GrabCut segmentation is inherently imperfect on real, noisy webcam
    footage (holes, jagged edges, occasional misses) - fine for nudging a
    colour average, but showing that mask itself as the 'best frame' image
    would show the operator a broken-looking silhouette instead of their
    garment. The actual displayed capture is always the untouched raw
    detector crop (see run_opencv_pipeline) - this function's output never
    reaches the frontend."""
    if image_crop is None or image_crop.size == 0:
        return None, None

    inset = _inset_crop(image_crop, margin)
    h, w = inset.shape[:2]
    scale = min(1.0, max_dim / max(h, w))
    work = cv2.resize(inset, (max(1, int(w * scale)), max(1, int(h * scale)))) if scale < 1.0 else inset.copy()

    fg_mask = _garment_foreground_mask(work)

    ys, xs = np.where(fg_mask)
    if len(ys) == 0:
        return work, np.ones(work.shape[:2], dtype=bool)

    # Tight crop to the mask's own bounding box, with a little breathing
    # room - keeps the colour sample concentrated on the garment without
    # needing to touch/fill any pixels (nothing here is ever displayed).
    pad = max(2, int(0.03 * max(work.shape[:2])))
    y1, y2 = max(0, ys.min() - pad), min(work.shape[0], ys.max() + 1 + pad)
    x1, x2 = max(0, xs.min() - pad), min(work.shape[1], xs.max() + 1 + pad)

    work = work[y1:y2, x1:x2]
    fg_mask = fg_mask[y1:y2, x1:x2]

    return work, fg_mask

def extract_colors_from_segment(display_bgr, fg_mask):
    """Colour clustering over an already-segmented garment image (see
    segment_garment) - the pixel selection work is done once and shared
    with whatever displays that same image, rather than repeated here."""
    if display_bgr is None or fg_mask is None or not fg_mask.any():
        return ["UNKNOWN"]

    blurred = cv2.GaussianBlur(display_bgr, (5, 5), 0)
    img_lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)

    # Only garment (foreground) pixels feed the clustering — background
    # (table/floor/hand/hair) pixels are excluded so they can never be
    # reported as a color.
    pixels_lab = img_lab[fg_mask]
    pixels_float = np.float32(pixels_lab)

    if len(pixels_float) == 0:
        return ["UNKNOWN"]

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    k = min(5, len(pixels_float))
    _, labels, centers = cv2.kmeans(pixels_float, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

    counts = np.bincount(labels.flatten())
    total = np.sum(counts)
    
    PALETTE_RGB = {
        "BLUE": (62, 111, 216), "NAVY": (31, 53, 104), "RED": (220, 50, 50),
        "BLACK": (35, 35, 35), "WHITE": (240, 240, 240), "GREEN": (63, 200, 100),
        "OLIVE": (107, 122, 79), "AMBER": (245, 178, 74), "YELLOW": (240, 210, 50),
        "ORANGE": (232, 130, 50), "GREY": (130, 130, 130), "BEIGE": (216, 201, 168),
        "BROWN": (138, 90, 50), "PURPLE": (138, 90, 201), "PINK": (232, 130, 176)
    }

    palette_lab = {}
    for name, rgb in PALETTE_RGB.items():
        rgb_arr = np.uint8([[[rgb[2], rgb[1], rgb[0]]]]) 
        lab_arr = cv2.cvtColor(rgb_arr, cv2.COLOR_BGR2LAB)
        palette_lab[name] = lab_arr[0][0]

    def closest_color_lab(lab_val):
        min_dist = float('inf')
        best_name = "UNKNOWN"
        for name, p_lab in palette_lab.items():
            dist = sum((float(a) - float(b)) ** 2 for a, b in zip(lab_val, p_lab))
            if dist < min_dist:
                min_dist = dist
                best_name = name
        return best_name

    raw_colors = []
    for i in range(k):
        pct = (counts[i] / total) * 100
        if pct > 1.5: 
            color_name = closest_color_lab(centers[i])
            raw_colors.append((color_name, pct))

    final_colors_dict = {}
    for name, pct in raw_colors:
        final_colors_dict[name] = final_colors_dict.get(name, 0) + pct

    final_colors = list(final_colors_dict.items())
    final_colors.sort(key=lambda x: x[1], reverse=True)

    if not final_colors:
        return ["UNKNOWN"]

    return [c[0] for c in final_colors]

def extract_colors(image_crop):
    """Convenience wrapper for a caller that only needs the colour list, not
    the segmented display image (segment_garment + extract_colors_from_segment
    is what the live capture loop uses so both share one segmentation pass)."""
    display, fg_mask = segment_garment(image_crop)
    return extract_colors_from_segment(display, fg_mask)

def _probe_cameras_generic(max_index=10):
    """Non-Windows fallback: OpenCV has no cross-platform "list device names"
    API, so this just tries opening each index in turn with the platform's
    default backend (AVFoundation on macOS, V4L2/GStreamer on Linux) and
    reports the ones that actually open. Indices are therefore guaranteed to
    open (same guarantee list_cameras() promises on Windows), just without a
    real device name - "Camera N" is the best available label."""
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            found.append(i)
        cap.release()
    return found


@app.route('/api/device/cameras', methods=['GET'])
def list_cameras():
    """Enumerates cameras. On Windows, via DirectShow (pygrabber) - the exact
    same backend switch_camera() uses, so the index returned here is
    guaranteed to open the device it's listed against, with its real name.
    Elsewhere, via a plain open-and-check probe (see
    _probe_cameras_generic) since there's no equivalent cross-platform
    device-name API in OpenCV alone. Re-enumerates fresh on every call, so a
    newly-plugged-in external webcam just appears next scan.

    Confirmed root cause of this route intermittently 500ing (reproduced
    directly): pygrabber's FilterGraph is built on comtypes, and COM
    requires each thread that touches it to call CoInitialize first. Flask's
    dev server spawns a brand-new thread per request, so a fresh thread's
    very first camera call failed every time with "CoInitialize has not
    been called" - not a concurrency race, a per-thread COM initialization
    that was simply never happening. Still serialized behind camera_lock
    (shared with switch_camera/stop_active_camera) as defense in depth,
    since DirectShow's Filter Graph Manager is separately not safe to touch
    from two threads at once even once each is CoInitialize'd."""
    with camera_lock:
        if IS_WINDOWS:
            comtypes.CoInitialize()
            try:
                devices = FilterGraph().get_input_devices()
            except Exception as e:
                return jsonify({"error": f"Could not enumerate cameras: {e}"}), 500
            finally:
                comtypes.CoUninitialize()
            return jsonify([{"index": i, "name": name} for i, name in enumerate(devices)])

        try:
            indices = _probe_cameras_generic()
        except Exception as e:
            return jsonify({"error": f"Could not enumerate cameras: {e}"}), 500
    return jsonify([{"index": i, "name": f"Camera {i}"} for i in indices])

@app.route('/api/device/test-camera', methods=['POST'])
def test_camera():
    """Switches the one shared camera capture to the given DirectShow index
    and confirms it's producing frames. Unlike a one-shot open-and-release,
    this capture is left running afterward - it becomes (or stays) the live
    feed the detection loop and /video_feed use, so passing this test and
    continuing to the dashboard never stops/restarts the camera."""
    data = request.get_json(silent=True) or {}
    index = data.get('index')
    if index is None:
        return jsonify({"success": False, "error": "Missing 'index' in request body."}), 400

    try:
        grabber = switch_camera(int(index))
    except RuntimeError:
        return jsonify({
            "success": False,
            "error": "Could not open this camera. It may be in use by another application.",
        })
    global camera_stopped_by
    camera_stopped_by = None

    frame = None
    for _ in range(20):  # up to ~2s for the grabber thread to produce a frame
        _, candidate = grabber.get_latest()
        if candidate is not None:
            frame = candidate
            break
        time.sleep(0.1)

    if frame is None:
        return jsonify({"success": False, "error": "Camera opened but did not return a frame."})

    # No need to capture/return an image here - reading a real frame is
    # enough to confirm the camera actually works, and the live feed on the
    # dashboard already shows it once the operator continues there.
    height, width = frame.shape[:2]
    return jsonify({"success": True, "width": width, "height": height})

def send_data_async(api_data):
    try:
        # 🔴 timeout=2 වෙනුවට timeout=5 ලෙස වෙනස් කළා
        requests.post(f"{BACKEND_API_BASE}/api/garments/", json=api_data, timeout=5)
        print("⚡ FAST DATA SENT TO BACKEND!")
    except Exception as e:
        print(f"❌ API Error: {e}")


def get_configured_camera_index(default=0, wait_seconds=0.0):
    """Reads the camera chosen in the Device Setup page. Falls back to
    `default` if nothing is configured yet. Electron starts the data API and
    this vision service at the same moment, so at startup the API may not be
    listening yet: `wait_seconds` keeps retrying for that long instead of
    immediately guessing camera 0 (which on a laptop is usually the built-in
    camera, not the packing-table webcam)."""
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            resp = requests.get(f"{BACKEND_API_BASE}/api/device/camera", timeout=2)
            if resp.status_code == 200:
                return resp.json().get("camera_index", default)
            return default  # API is up but no camera has been saved yet
        except Exception as e:
            if time.monotonic() >= deadline:
                print(f"ℹ️ Could not fetch configured camera (using default {default}): {e}")
                return default
            time.sleep(0.5)

class FrameGrabber:
    """Reads frames from the camera in its own thread so a slow inference
    cycle never blocks frame acquisition - the main loop always processes
    the most recently grabbed frame instead of a stale queued one."""

    def __init__(self, cap):
        self.cap = cap
        self.lock = threading.Lock()
        self.frame = None
        self.frame_id = 0
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            if not self.cap.isOpened():
                self.running = False
                break
            ret, frame = self.cap.read()
            if not ret:
                continue
            with self.lock:
                self.frame = frame
                self.frame_id += 1

    def get_latest(self):
        with self.lock:
            return self.frame_id, self.frame

    def stop(self):
        self.running = False


# ============================================================================
# SHARED CAMERA STATE
#
# Device Setup's "Test Camera" and the live detection loop used to each open
# their own independent cv2.VideoCapture - testing a camera never affected
# what the dashboard showed, and switching cameras required restarting the
# whole process. Now there's exactly one active capture, owned here, that
# both read from - testing a camera IS switching the live one, instantly.
# ============================================================================

camera_lock = threading.Lock()
# Why the camera is currently off: None (it is on, or never opened), "system"
# (the desktop app released it when the operator switched to another feature)
# or "operator" (turned off on purpose from the Downtime Log). The Live
# Dashboard turns a "system"-stopped camera back on by itself, but leaves an
# operator's deliberate stop alone.
camera_stopped_by = None
active_grabber = None
active_camera_index = None
active_frame_w = 0
active_frame_h = 0

def switch_camera(index):
    """Opens (or reuses) `index` as the one shared capture. Raises RuntimeError
    if the camera can't be opened after retrying - callers decide how to
    react (fall back to another index, report an error, etc.)."""
    global active_grabber, active_camera_index, active_frame_w, active_frame_h

    with camera_lock:
        if active_grabber is not None and active_camera_index == index and active_grabber.running:
            return active_grabber

        if active_grabber is not None:
            active_grabber.stop()
            joined_cleanly = True
            active_grabber.thread.join(timeout=1.0)
            if active_grabber.thread.is_alive():
                # The grab thread is still inside a blocking cap.read() -
                # releasing the capture out from under it is a real race
                # (can hang or corrupt the device's DirectShow state, which
                # is a plausible cause of a *subsequent* open failing with
                # "could not open this camera" until the whole process is
                # restarted). Release anyway - there is no safe alternative
                # since the device must be freed before reopening - but
                # give the thread a bit longer to notice `running = False`
                # and exit on its own before pulling the capture out from
                # under it.
                joined_cleanly = False
                active_grabber.thread.join(timeout=1.5)
            active_grabber.cap.release()
            active_grabber = None
            active_camera_index = None
            # DirectShow on Windows can transiently refuse to reopen a
            # device immediately after it was just released (the driver
            # needs a moment to actually free it) - a brief pause here
            # avoids spurious "could not open this camera" failures that
            # would otherwise succeed a moment later. Give it longer if the
            # grabber thread didn't confirm a clean stop above.
            time.sleep(0.3 if joined_cleanly else 0.8)

        # Opening can also transiently fail even on a device nothing else
        # is using yet (freshly plugged in, waking from a previous close) -
        # retry a couple of times before reporting failure rather than
        # giving up after a single attempt.
        cap = None
        for attempt in range(3):
            # CAP_DSHOW is what list_cameras() promises the index will open
            # with on Windows; elsewhere OpenCV's own default backend
            # (AVFoundation on macOS, V4L2/GStreamer on Linux) is the only
            # generally-available option.
            candidate = cv2.VideoCapture(index, cv2.CAP_DSHOW) if IS_WINDOWS else cv2.VideoCapture(index)
            if candidate.isOpened():
                cap = candidate
                break
            candidate.release()
            if attempt < 2:
                time.sleep(0.4)

        if cap is None:
            raise RuntimeError(f"Could not open camera index {index}")

        active_frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        active_frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480

        active_grabber = FrameGrabber(cap)
        active_camera_index = index
        return active_grabber

def get_active_camera():
    """Returns (grabber, index, frame_w, frame_h) - grabber is None if no
    camera has been successfully opened yet."""
    with camera_lock:
        return active_grabber, active_camera_index, active_frame_w, active_frame_h

def stop_active_camera():
    """Releases the shared camera, if one is open. The detection loop just
    idles (see run_opencv_pipeline's `if grabber is None` branch) until a
    camera is opened again via Device Setup - used for the Downtime Log's
    'turn off camera' control, e.g. during a machine breakdown or power
    failure when the line isn't running."""
    global active_grabber, active_camera_index, active_frame_w, active_frame_h

    with camera_lock:
        was_running = active_grabber is not None
        if active_grabber is not None:
            active_grabber.stop()
            active_grabber.thread.join(timeout=1.0)
            if active_grabber.thread.is_alive():
                # Same race as in switch_camera - give the grab loop a
                # little longer to notice it should stop before the
                # capture gets released out from under it.
                active_grabber.thread.join(timeout=1.5)
            active_grabber.cap.release()
        active_grabber = None
        active_camera_index = None
        active_frame_w = 0
        active_frame_h = 0
        return was_running

@app.route('/api/device/stop-camera', methods=['POST'])
def stop_camera_route():
    global camera_stopped_by, global_frame
    data = request.get_json(silent=True) or {}
    was_running = stop_active_camera()
    camera_stopped_by = "operator" if data.get("reason") == "operator" else "system"
    # Drop the last picture so the stream never shows a frozen frame as if
    # it were live while the camera is off.
    with lock:
        global_frame = None
    set_pipeline_status("EMPTY", detail="Camera is turned off")
    return jsonify({"success": True, "was_running": was_running, "stopped_by": camera_stopped_by})


@app.route('/api/device/start-camera', methods=['POST'])
def start_camera_route():
    """Turns the saved Device Setup camera back on (or the index given in the
    body). Used by the Live Dashboard when it opens and finds the camera off,
    e.g. after the operator switched to another feature and came back."""
    global camera_stopped_by
    data = request.get_json(silent=True) or {}
    index = data.get('index')
    if index is None:
        index = get_configured_camera_index(default=0, wait_seconds=3.0)
    try:
        grabber = switch_camera(int(index))
    except (RuntimeError, ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": f"Could not open camera {index}. It may be unplugged or in use by another application - choose a camera in Device Setup.",
        })
    camera_stopped_by = None
    for _ in range(30):  # up to ~3 s for the first frame
        _, frame = grabber.get_latest()
        if frame is not None:
            height, width = frame.shape[:2]
            return jsonify({"success": True, "index": int(index), "width": width, "height": height})
        time.sleep(0.1)
    return jsonify({"success": False, "error": "Camera opened but did not return a picture."})


# ============================================================================
# LIVE PIPELINE STATUS (for the dashboard's real-time status badge)
# ============================================================================

pipeline_status_lock = threading.Lock()
pipeline_status = {
    "state": "STARTING",
    "detected_style": None,
    "confidence": None,
    "detail": "Starting camera...",
    "progress": None,
    "calibrated": False,
}

def set_pipeline_status(state, detected_style=None, confidence=None, detail=None, progress=None, calibrated=None):
    global pipeline_status
    with pipeline_status_lock:
        pipeline_status = {
            "state": state,
            "detected_style": detected_style,
            "confidence": confidence,
            "detail": detail,
            "progress": list(progress) if progress else None,
            "calibrated": pipeline_status.get("calibrated", False) if calibrated is None else calibrated,
        }

@app.route('/api/pipeline/status', methods=['GET'])
def get_pipeline_status():
    # camera_active is computed live from the shared camera state (not
    # cached in pipeline_status) so it's accurate immediately after
    # stop-camera or a Device Setup switch, not just whenever the detection
    # loop last happened to run.
    grabber, _, _, _ = get_active_camera()
    with pipeline_status_lock:
        status = dict(pipeline_status)
    status["camera_active"] = grabber is not None and grabber.running
    status["camera_stopped_by"] = None if status["camera_active"] else camera_stopped_by
    return jsonify(status)


# Requests from Flask threads to the detection thread. The engine is only
# ever touched by the detection thread; these flags are how other threads ask
# it to do something.
recalibrate_requested = threading.Event()

@app.route('/api/pipeline/recalibrate', methods=['POST'])
def recalibrate_route():
    """Re-learn the picture of the empty folding zone (after the light
    changed, the camera was nudged, or the table was rearranged). The zone
    should be empty when this is pressed; learning completes after about one
    second of stillness."""
    recalibrate_requested.set()
    set_pipeline_status("CALIBRATING", detail="Keep the folding zone empty and still", calibrated=False)
    return jsonify({"success": True})


# ============================================================================
# DETECTION LOOP
# ============================================================================

STATE_COLOURS = {
    "CALIBRATING": (200, 200, 200),
    "EMPTY": (160, 160, 160),
    "DETECTING": (0, 165, 255),
    "ANALYSING": (0, 220, 255),
    "UNCERTAIN": (0, 120, 255),
    "CAPTURED": (0, 200, 0),
    "WAITING_REMOVAL": (255, 0, 255),
}

def colours_for_capture(capture):
    """Dominant colours of the captured garment. The engine already knows
    which pixels of the crop are garment (they differ from the empty table
    and are not skin), which is a better sample than GrabCut's guess - it is
    used when it covers a sensible share of the crop, otherwise the original
    GrabCut segmentation is the fallback."""
    crop = capture.image
    mask = capture.mask
    if mask is not None and mask.shape[:2] == crop.shape[:2]:
        garment = mask & ~_skin_mask(crop)
        if garment.mean() >= 0.15:
            return extract_colors_from_segment(crop, garment)
    colors_crop, fg_mask = segment_garment(crop)
    return extract_colors_from_segment(colors_crop, fg_mask)


def draw_overlay(display_frame, result):
    font = cv2.FONT_HERSHEY_SIMPLEX
    colour = STATE_COLOURS.get(result.state, (255, 255, 255))
    if result.roi:
        x1, y1, x2, y2 = result.roi
        cv2.rectangle(display_frame, (x1, y1), (x2, y2), (255, 100, 0), 2, cv2.LINE_AA)
        cv2.putText(display_frame, "FOLDING ZONE", (x1 + 4, y2 - 8), font, 0.45, (255, 100, 0), 1, cv2.LINE_AA)
    if result.box:
        x1, y1, x2, y2 = result.box
        cv2.rectangle(display_frame, (x1, y1), (x2, y2), colour, 2, cv2.LINE_AA)
        if result.style and result.state in ("ANALYSING", "UNCERTAIN", "CAPTURED", "WAITING_REMOVAL"):
            prefix = "" if result.state in ("CAPTURED", "WAITING_REMOVAL") else "? "
            label = f"{prefix}{result.style} ({(result.confidence or 0):.0f}%)"
            cv2.putText(display_frame, label, (x1, max(18, y1 - 7)), font, 0.6, colour, 2, cv2.LINE_AA)
    banner = f"{result.state}: {result.detail}"
    cv2.putText(display_frame, banner, (14, 30), font, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(display_frame, banner, (14, 30), font, 0.6, colour, 2, cv2.LINE_AA)


def run_opencv_pipeline():
    global global_frame

    configured_index = get_configured_camera_index(default=0, wait_seconds=10.0)
    if camera_stopped_by is not None:
        # The desktop app released the camera (operator left the feature)
        # while this service was still starting - do not grab it back.
        print("ℹ️ Camera was released before startup finished - waiting for the Live Dashboard to turn it on.")
    else:
        print(f"Attempting to open camera index {configured_index} (from Device Setup, or default)...")
        try:
            switch_camera(configured_index)
        except RuntimeError:
            print("⚠️ Configured camera failed. Trying Default Camera (Index 0)...")
            try:
                switch_camera(0)
            except RuntimeError:
                print("❌ Error: Could not open any webcam. Please check connections.")
                set_pipeline_status("EMPTY", detail="No camera could be opened - choose one in Device Setup")

    # First YOLO call after process start pays a one-time warm-up cost (model
    # graph setup, thread pool init) that can run into several seconds. Pay
    # that cost now, during camera setup, instead of letting it land on
    # whichever real garment happens to be first on the line.
    print("Warming up inference engine...")
    style_classifier(np.zeros((480, 640, 3), dtype=np.uint8))
    print("Ready.")

    print("\n" + "=" * 50)
    print("🏭 AI PIPELINE: SETTLED-GARMENT STYLE VOTING ACTIVE")
    print("=" * 50 + "\n")

    active_index = None
    active_grabber_ref = None
    last_seen_frame_id = -1

    while True:
        grabber, cam_index, _, _ = get_active_camera()
        if grabber is None or not grabber.running:
            # No camera active yet (or it just got swapped out) - wait for
            # Device Setup or the startup logic above to open one.
            time.sleep(0.2)
            continue

        if cam_index != active_index:
            # A different camera sees a different table: forget the learned
            # empty-zone picture and any detection progress.
            style_engine.reset()
            active_index = cam_index
        if grabber is not active_grabber_ref:
            # A freshly (re)opened capture numbers its frames from 1 again.
            active_grabber_ref = grabber
            last_seen_frame_id = -1

        if recalibrate_requested.is_set():
            recalibrate_requested.clear()
            style_engine.request_calibration()

        frame_id, frame = grabber.get_latest()
        if frame is None or frame_id == last_seen_frame_id:
            # No new frame since the last loop iteration yet - avoid
            # re-processing a frame we already handled.
            time.sleep(0.005)
            continue
        last_seen_frame_id = frame_id

        try:
            result = style_engine.process(frame, time.monotonic())
        except Exception as error:  # never let one bad frame kill the service
            print(f"❌ Style engine error: {error}")
            # Keep the live picture flowing even if analysis failed.
            set_pipeline_status("DETECTING", detail=f"Analysis error - see vision log ({type(error).__name__})")
            with lock:
                global_frame = frame.copy()
            time.sleep(0.05)
            continue

        if result.capture is not None:
            capture = result.capture
            colors_list = colours_for_capture(capture)
            _, buffer = cv2.imencode('.jpg', capture.image)
            api_data = {
                "style_name": capture.style,
                "main_color": colors_list[0],
                "other_colors": ",".join(colors_list[1:]) if len(colors_list) > 1 else "",
                "confidence": round(capture.confidence * 100, 2),
                "image_base64": base64.b64encode(buffer).decode('utf-8'),
            }
            print(f"📦 Captured {capture.style} {api_data['confidence']}% (agreement {capture.agreement * 100:.0f}%, scores {capture.class_scores})")
            threading.Thread(target=send_data_async, args=(api_data,), daemon=True).start()

        set_pipeline_status(
            result.state,
            result.style,
            result.confidence,
            detail=result.detail,
            progress=result.progress,
            calibrated=result.calibrated,
        )

        display_frame = frame.copy()
        draw_overlay(display_frame, result)
        with lock:
            global_frame = display_frame

def run_service():
    t = threading.Thread(target=run_opencv_pipeline)
    t.daemon = True
    t.start()
    # threaded=True: /video_feed is a long-lived streaming connection - without
    # this, Flask's dev server (single request at a time by default) would
    # block every other route (garment posts, the Demo video-upload analysis)
    # for as long as anyone has the live dashboard open.
    vision_port = int(os.environ.get("THREADSCAN_VISION_PORT", "5050"))
    app.run(host='127.0.0.1', port=vision_port, debug=False, use_reloader=False, threaded=True)


if __name__ == '__main__':
    run_service()
