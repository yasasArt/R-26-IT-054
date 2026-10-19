import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectDirectory = path.resolve(frontendDirectory, "..");
const backendDirectory = path.join(projectDirectory, "backend", "garment-style-colour-backend");
const read = (...parts: string[]) => readFileSync(path.join(...parts), "utf8");

test("live style detection decides through the settled-garment engine", () => {
  const pipeline = read(backendDirectory, "live_webcam_pipeline.py");
  const engine = read(backendDirectory, "style_engine.py");

  assert.match(pipeline, /from style_engine import EngineConfig, StyleCaptureEngine, YoloStyleClassifier/);
  assert.match(pipeline, /style_engine\.process\(frame, time\.monotonic\(\)\)/);
  assert.match(pipeline, /@app\.route\('\/api\/pipeline\/recalibrate', methods=\['POST'\]\)/);
  // The old rule re-captured the same garment while it was being folded.
  assert.doesNotMatch(pipeline, /AUTO_UNLOCK_FRAMES/);
  // Crops are classified at the model's training resolution.
  assert.match(pipeline, /THREADSCAN_CLASSIFY_IMGSZ", "640"/);

  for (const rule of ["class BackgroundModel", "def _outline_is_stable", "def _hand_pixels", "def _is_ghost", "min_agreement", "empty_seconds"]) {
    assert.match(engine, new RegExp(rule));
  }
});

test("style analytics charts name both axes", () => {
  const analytics = read(frontendDirectory, "garment-style-colour-frontend", "components", "Analytics.tsx");
  for (const title of [
    "Production date",
    "Garments packed (pcs)",
    "Garment style",
    "Pieces (pcs)",
    "Main colour",
    "Garments scanned (pcs)",
  ]) {
    assert.match(analytics, new RegExp(title.replace(/[()]/g, "\\$&")));
  }
  assert.match(analytics, /precision: 0/);
  // The daily output chart is the large, primary chart on the page.
  assert.match(analytics, /height="h-\[480px\]"/);
  assert.doesNotMatch(analytics, /Detection Confidence by Style/);
});

test("history log shows the captured style as read-only text", () => {
  const history = read(frontendDirectory, "garment-style-colour-frontend", "components", "HistoryLog.tsx");
  assert.doesNotMatch(history, /<select/);
  assert.match(history, /\{styleName\(scan\.style_name\)\}/);
});

test("the live dashboard gives the camera panel the full width", () => {
  const app = read(frontendDirectory, "garment-style-colour-frontend", "App.tsx");
  assert.doesNotMatch(app, /grid-cols-\[1fr_360px\]/);
  // The panel clips its overflow, so as a direct child of the scrolling
  // flex column it would be squashed to a thin line; a wrapper keeps it whole.
  assert.match(app, /<div className="shrink-0">\s*<LiveCameraPanel scan=\{latestScan\} \/>/);
  // Alerts stay available on their own page.
  assert.match(app, /activeTab === "alerts"/);
});

test("the live camera feed recovers after a feature switch or a dropped stream", () => {
  const pipeline = read(backendDirectory, "live_webcam_pipeline.py");
  const panel = read(frontendDirectory, "garment-style-colour-frontend", "components", "LiveCameraPanel.tsx");
  const downtime = read(frontendDirectory, "garment-style-colour-frontend", "components", "DowntimeLog.tsx");

  // Backend: the saved camera can be turned back on, and the reason it was
  // turned off is reported so only deliberate operator stops are respected.
  assert.match(pipeline, /@app\.route\('\/api\/device\/start-camera', methods=\['POST'\]\)/);
  assert.match(pipeline, /status\["camera_stopped_by"\]/);
  assert.match(pipeline, /get_configured_camera_index\(default=0, wait_seconds=10\.0\)/);

  // Frontend: auto turn-on, a manual button, and a retrying stream - never a
  // DOM-edited "offline" cover that React cannot remove again.
  assert.match(panel, /result\.camera_stopped_by !== "operator"/);
  assert.match(panel, /Turn camera on/);
  assert.match(panel, /onError=\{handleFeedError\}/);
  assert.doesNotMatch(panel, /classList\.remove\("hidden"\)/);
  assert.match(downtime, /stopCamera\("operator"\)/);
});

