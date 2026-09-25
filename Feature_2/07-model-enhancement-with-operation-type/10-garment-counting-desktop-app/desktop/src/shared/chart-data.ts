import type { PieceEvent, TargetPoint } from "./types";

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

export function getProgressPercent(produced: number, target: number): number {
  if (target <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((produced / target) * 100)));
}
