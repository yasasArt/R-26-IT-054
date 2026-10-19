import type { IotEvent, PieceEvent, TargetPoint } from "./types";

export interface CycleChartPoint {
  pieceNumber: number;
  cycleSeconds: number;
  label: string;
}

export function buildCycleChartData(events: readonly PieceEvent[], limit = 30): CycleChartPoint[] {
  return [...events]
    .filter((event) => Number.isFinite(event.cycle_seconds) && event.cycle_seconds >= 0)
    .sort((left, right) => left.piece_number - right.piece_number)
    .slice(-limit)
    .map((event) => ({
      pieceNumber: event.piece_number,
      cycleSeconds: Number(event.cycle_seconds.toFixed(2)),
      label: `#${event.piece_number}`,
    }));
}

export function buildTargetCountdown(target: number, events: readonly PieceEvent[]): TargetPoint[] {
  const safeTarget = Math.max(0, target);
  const orderedEvents = [...events].sort((left, right) => left.piece_number - right.piece_number);

  return [
    { piece_number: 0, remaining_pieces: safeTarget },
    ...orderedEvents.map((event) => ({
      piece_number: event.piece_number,
      remaining_pieces: Math.max(0, safeTarget - event.piece_number),
    })),
  ];
}

export interface PacePoint {
  elapsedSeconds: number;
  actualPieces: number;
  expectedPieces: number;
  paused: boolean;
}

export interface PacePause {
  startSeconds: number;
  endSeconds: number;
}

export interface PaceChartData {
  points: PacePoint[];
  pauses: PacePause[];
  elapsedSeconds: number;
  productiveSeconds: number;
  actualPieces: number;
  expectedPieces: number;
}

/** Compare cumulative output against the selected cycle estimate in wall-clock time.
 * Rework, downtime and lost controller connection stop the expected clock; overlapping
 * pauses are counted only once. All timestamps come from the existing session API.
 */
export function buildProductionPace(
  startedAt: string,
  endedAt: string | null,
  estimateSeconds: number | null,
  pieces: readonly PieceEvent[],
  events: readonly IotEvent[],
  now = Date.now(),
): PaceChartData {
  const start = Date.parse(startedAt);
  const end = endedAt === null ? now : Date.parse(endedAt);
  const validStart = Number.isFinite(start) ? start : now;
  const validEnd = Number.isFinite(end) ? Math.max(validStart, end) : validStart;
  const duration = validEnd - validStart;
  const timeline: Array<{ time: number; kind: "piece" | "event" | "end"; event?: IotEvent }> = [];

  for (const piece of pieces) {
    const time = Date.parse(piece.completed_at);
    if (Number.isFinite(time) && time >= validStart && time <= validEnd) {
      timeline.push({ time, kind: "piece" });
    }
  }
  for (const event of events) {
    const time = Date.parse(event.occurred_at);
    if (Number.isFinite(time) && time >= validStart && time <= validEnd) {
      timeline.push({ time, kind: "event", event });
    }
  }
  timeline.push({ time: validEnd, kind: "end" });
  timeline.sort((a, b) => a.time - b.time);

  const estimate = estimateSeconds !== null && Number.isFinite(estimateSeconds) && estimateSeconds > 0
    ? estimateSeconds : null;
  const points: PacePoint[] = [{ elapsedSeconds: 0, actualPieces: 0, expectedPieces: 0, paused: false }];
  const pauses: PacePause[] = [];
  let lastTime = validStart;
  let productiveMs = 0;
  let actualPieces = 0;
  let operatorMode: "NORMAL" | "REWORK" | "DOWNTIME" = "NORMAL";
  let disconnected = false;
  let pauseStart: number | null = null;

  for (let index = 0; index < timeline.length;) {
    const time = timeline[index].time;
    if (operatorMode === "NORMAL" && !disconnected) productiveMs += time - lastTime;
    lastTime = time;
    while (index < timeline.length && timeline[index].time === time) {
      const item = timeline[index];
      if (item.kind === "piece") actualPieces += 1;
      if (item.kind === "event") {
        const type = item.event?.event_type;
        if (type === "REWORK" || type === "DOWNTIME") operatorMode = type;
        if (type === "RESET") operatorMode = "NORMAL";
        if (type === "DISCONNECTED") disconnected = true;
        if (type === "RECONNECTED") disconnected = false;
      }
      index += 1;
    }
    const paused = operatorMode !== "NORMAL" || disconnected;
    const elapsedSeconds = (time - validStart) / 1000;
    if (paused && pauseStart === null) pauseStart = elapsedSeconds;
    if (!paused && pauseStart !== null) {
      pauses.push({ startSeconds: pauseStart, endSeconds: elapsedSeconds });
      pauseStart = null;
    }
    points.push({
      elapsedSeconds,
      actualPieces,
      expectedPieces: estimate === null ? 0 : productiveMs / 1000 / estimate,
      paused,
    });
  }
  if (pauseStart !== null) pauses.push({ startSeconds: pauseStart, endSeconds: duration / 1000 });

  return {
    points, pauses, elapsedSeconds: duration / 1000, productiveSeconds: productiveMs / 1000,
    actualPieces, expectedPieces: estimate === null ? 0 : productiveMs / 1000 / estimate,
  };
}

export function getProgressPercent(produced: number, target: number): number {
  if (target <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((produced / target) * 100)));
}
