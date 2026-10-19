import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (...parts: string[]) => readFileSync(path.join(frontendDirectory, ...parts), "utf8");

test("the renderer security policy allows the rework video stream", () => {
  const page = read("src", "renderer", "index.html");
  // forge.config.ts allows garmentrework: in its dev header; the page's own
  // meta policy must allow it too, or the browser blocks the Rework video.
  assert.match(page, /img-src [^;]*\bgarmentrework:/);
  assert.match(page, /media-src [^;]*\bgarmentrework:/);
});

test("the rework stream proxy only time-limits connecting, not the endless video body", () => {
  const manager = read("src", "main", "feature-backend-manager.ts");
  const openStream = manager.slice(manager.indexOf("async openStream("), manager.indexOf("stop(): void"));
  assert.doesNotMatch(openStream, /signal:\s*AbortSignal\.timeout/);
  assert.match(openStream, /clearTimeout\(connectTimer\)/);
});

test("rework analysis shows a labelled trend chart and no verdict split card", () => {
  const analysis = read("garment-rework-frontend", "views", "Analysis.jsx");
  assert.doesNotMatch(analysis, /Live Verdict Split/);
  assert.match(analysis, /Video frame \(inspection progress\)/);
  assert.match(analysis, /Pieces counted \(pcs\)/);
});

test("rework video files can be reviewed at 1x, 2x or 3x speed", () => {
  const live = read("garment-rework-frontend", "views", "LiveProduction.jsx");
  const backend = readFileSync(path.join(frontendDirectory, "..", "backend", "garment-rework-backend", "main.py"), "utf8");
  // Speed control only for video files, sent through already-allowed routes.
  assert.match(live, /sourceType === 'video' && \(/);
  assert.match(live, /\[1, 2, 3\]\.map\(\(speed\)/);
  assert.match(live, /playback_speed: sourceType === 'video' \? playbackSpeed : 1/);
  assert.match(live, /playback_speed: playbackSpeed/);
  // Backend skips frames for files only and never above 3x.
  assert.match(backend, /MAX_PLAYBACK_SPEED = 3/);
  assert.match(backend, /if state\.source_is_file and state\.playback_speed > 1:/);
  assert.match(backend, /state\.frame_idx \+= 1 \+ skipped/);
});

test("current session log card matches the historical sessions card", () => {
  const analysis = read("garment-rework-frontend", "views", "Analysis.jsx");
  // Same fixed header height on both cards, so titles and tables line up.
  assert.equal((analysis.match(/h-\[68px\] shrink-0 px-5 border-b border-line flex justify-between items-center gap-4 bg-canvas/g) ?? []).length, 2);
  assert.match(analysis, />Piece ID</);
  assert.doesNotMatch(analysis, /w-1\/4/);
});
