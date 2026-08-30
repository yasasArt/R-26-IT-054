import assert from "node:assert/strict";
import test from "node:test";

import { buildCycleChartData, buildTargetCountdown, getProgressPercent } from "../src/shared/chart-data.ts";
import type { PieceEvent } from "../src/shared/types.ts";

function piece(pieceNumber: number, cycleSeconds: number): PieceEvent {
  return {
    id: pieceNumber,
    session_id: 1,
    piece_number: pieceNumber,
    cycle_seconds: cycleSeconds,
    sewing_started_at: null,
    completed_at: "2026-08-22T08:00:00.000Z",
    state_from: "SEWING",
    state_to: "IDLE_SETUP",
    confidence: 0.94,
    event_source: "VALIDATION",
    created_at: "2026-08-22T08:00:00.000Z",
  };
}

test("the cycle chart always retains the measured first garment", () => {
  const points = buildCycleChartData([piece(2, 21.4), piece(1, 18.75)]);
  assert.deepEqual(points.map((point) => point.pieceNumber), [1, 2]);
  assert.equal(points[0].cycleSeconds, 18.75);
});

test("the target countdown starts at the target and steps down for every piece", () => {
  assert.deepEqual(buildTargetCountdown(3, [piece(1, 12), piece(2, 14)]), [
    { piece_number: 0, remaining_pieces: 3 },
    { piece_number: 1, remaining_pieces: 2 },
    { piece_number: 2, remaining_pieces: 1 },
  ]);
});

test("the target countdown never becomes negative after overproduction", () => {
  const points = buildTargetCountdown(1, [piece(1, 12), piece(2, 14)]);
  assert.equal(points[points.length - 1].remaining_pieces, 0);
});

test("operator progress is clamped to a readable 0-to-100-percent range", () => {
  assert.equal(getProgressPercent(5, 10), 50);
  assert.equal(getProgressPercent(12, 10), 100);
  assert.equal(getProgressPercent(0, 0), 0);
});
