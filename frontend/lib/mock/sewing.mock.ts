// lib/mock/sewing.mock.ts
import type { IDetectionEvent, ICycleRecord, IDemoScriptStep } from "@/lib/types";
import { generateId, randomBetween, randomFloat } from "@/lib/utils";
import { CYCLE_TIME } from "@/lib/constants";

// ─────────────────────────────────────────
// GENERATORS
// ─────────────────────────────────────────

export function generateDetectionEvent(
  pieceNumber: number,
  overrides: Partial<IDetectionEvent> = {}
): IDetectionEvent {
  const cycleTime = randomBetween(
    CYCLE_TIME.TARGET_SECONDS - 5,
    CYCLE_TIME.WARNING_SECONDS + 10
  );
  return {
    id: generateId("det"),
    timestamp: new Date(),
    pieceNumber,
    cycleTimeSeconds: cycleTime,
    operatorStatus: "active",
    confidenceScore: randomFloat(0.78, 0.99),
    signalA: true,
    signalB: true,
    ...overrides,
  };
}

export function generateCycleRecord(
  pieceNumber: number,
  cycleTimeSeconds?: number
): ICycleRecord {
  const duration = cycleTimeSeconds ?? randomBetween(35, 80);
  return {
    id: generateId("cyc"),
    timestamp: new Date(),
    pieceNumber,
    durationSeconds: duration,
    isWithinTarget: duration <= CYCLE_TIME.TARGET_SECONDS,
  };
}

/** Generates a seed of N past detection events for initial chart data */
export function generateSeedDetections(count: number): IDetectionEvent[] {
  const events: IDetectionEvent[] = [];
  const now = Date.now();

  for (let i = 0; i < count; i++) {
    const minutesAgo = (count - i) * 0.8;
    const ts = new Date(now - minutesAgo * 60 * 1000);
    const cycleTime = randomBetween(32, 75);

    events.push({
      id: generateId("det"),
      timestamp: ts,
      pieceNumber: i + 1,
      cycleTimeSeconds: cycleTime,
      operatorStatus: "active",
      confidenceScore: randomFloat(0.78, 0.99),
      signalA: true,
      signalB: true,
    });
  }
  return events;
}

export function generateSeedCycleHistory(count: number): ICycleRecord[] {
  const now = Date.now();
  return Array.from({ length: count }, (_, i) => {
    const minutesAgo = (count - i) * 0.8;
    const duration = randomBetween(32, 78);
    return {
      id: generateId("cyc"),
      timestamp: new Date(now - minutesAgo * 60 * 1000),
      pieceNumber: i + 1,
      durationSeconds: duration,
      isWithinTarget: duration <= CYCLE_TIME.TARGET_SECONDS,
    };
  });
}

// ─────────────────────────────────────────
// DEMO SCRIPTS
// ─────────────────────────────────────────

export const SEWING_DEMO_SCRIPT_NORMAL: IDemoScriptStep[] = [
  { id: "s1", delay: 0,    action: "incrementPiece",  label: "Piece #1 detected", payload: { cycleTime: 42 } },
  { id: "s2", delay: 4000, action: "incrementPiece",  label: "Piece #2 detected", payload: { cycleTime: 38 } },
  { id: "s3", delay: 4000, action: "incrementPiece",  label: "Piece #3 detected", payload: { cycleTime: 44 } },
  { id: "s4", delay: 4000, action: "incrementPiece",  label: "Piece #4 detected", payload: { cycleTime: 46 } },
  { id: "s5", delay: 3500, action: "incrementPiece",  label: "Piece #5 detected", payload: { cycleTime: 39 } },
];

export const SEWING_DEMO_SCRIPT_REWORK: IDemoScriptStep[] = [
  { id: "r1", delay: 0,    action: "incrementPiece",  label: "Piece #1 detected", payload: { cycleTime: 43 } },
  { id: "r2", delay: 3500, action: "startRework",     label: "Rework triggered by operator" },
  { id: "r3", delay: 5000, action: "incrementPiece",  label: "Piece #2 (rework) detected", payload: { cycleTime: 78 } },
  { id: "r4", delay: 3000, action: "endRework",       label: "Rework resolved" },
  { id: "r5", delay: 2500, action: "incrementPiece",  label: "Piece #3 detected", payload: { cycleTime: 41 } },
];

export const SEWING_DEMO_SCRIPT_DOWNTIME: IDemoScriptStep[] = [
  { id: "d1", delay: 0,    action: "incrementPiece",  label: "Piece #1 detected", payload: { cycleTime: 40 } },
  { id: "d2", delay: 3000, action: "startDowntime",   label: "Downtime started — thread break" },
  { id: "d3", delay: 8000, action: "endDowntime",     label: "Downtime resolved" },
  { id: "d4", delay: 2000, action: "incrementPiece",  label: "Piece #2 detected", payload: { cycleTime: 45 } },
  { id: "d5", delay: 4000, action: "incrementPiece",  label: "Piece #3 detected", payload: { cycleTime: 43 } },
];