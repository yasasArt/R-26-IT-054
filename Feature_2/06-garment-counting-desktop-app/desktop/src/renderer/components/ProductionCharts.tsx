import { buildCycleChartData } from "../../shared/chart-data";
import type { PieceEvent, TargetPoint } from "../../shared/types";
import { formatNumber } from "../lib/format";
import { EmptyState } from "./OperatorUi";

const WIDTH = 500;
const HEIGHT = 235;
const LEFT = 44;
const RIGHT = 16;
const TOP = 18;
const BOTTOM = 34;

function chartY(value: number, max: number): number {
  return HEIGHT - BOTTOM - (value / Math.max(1, max)) * (HEIGHT - TOP - BOTTOM);
}

function Grid({ maximum }: { maximum: number }) {
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <g>
      {ticks.map((fraction) => {
        const value = maximum * fraction;
        const y = chartY(value, maximum);
        return (
          <g key={fraction}>
            <line x1={LEFT} x2={WIDTH - RIGHT} y1={y} y2={y} className="chart-grid-line" />
            <text x={LEFT - 8} y={y + 4} textAnchor="end" className="chart-axis-label">{formatNumber(value, value < 10 ? 1 : 0)}</text>
          </g>
        );
      })}
    </g>
  );
}

export function CycleTimeChart({ events }: { events: PieceEvent[] }) {
  const data = buildCycleChartData(events);

  if (!data.length) {
    return <EmptyState icon="clock" title="Waiting for the first garment" description="The first completed piece and every piece after it will appear here with a measured cycle time." />;
  }

  const maximum = Math.max(...data.map((point) => point.cycleSeconds), 1) * 1.18;
  const innerWidth = WIDTH - LEFT - RIGHT;
  const slotWidth = innerWidth / data.length;
  const barWidth = Math.min(42, Math.max(8, slotWidth - 9));
  const average = data.reduce((sum, point) => sum + point.cycleSeconds, 0) / data.length;

  return (
    <>
      <svg className="production-chart" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Cycle time in seconds for every completed garment">
        <Grid maximum={maximum} />
        {data.map((point, index) => {
          const x = LEFT + slotWidth * index + (slotWidth - barWidth) / 2;
          const y = chartY(point.cycleSeconds, maximum);
          return (
            <g key={point.pieceNumber}>
              <rect x={x} y={y} width={barWidth} height={HEIGHT - BOTTOM - y} rx={5} className="cycle-bar" />
              {(data.length < 13 || index % Math.ceil(data.length / 10) === 0) ? (
                <text x={x + barWidth / 2} y={HEIGHT - 13} textAnchor="middle" className="chart-axis-label">{point.label}</text>
              ) : null}
              <title>{`Piece ${point.pieceNumber}: ${formatNumber(point.cycleSeconds, 2)} seconds`}</title>
            </g>
          );
        })}
      </svg>
      <div className="chart-footer"><span>Includes piece #1</span><strong>Average {formatNumber(average, 1)} sec</strong></div>
    </>
  );
}

export function TargetCountdownChart({ points, target }: { points: TargetPoint[]; target: number }) {
  const maximum = Math.max(target, 1);
  const innerWidth = WIDTH - LEFT - RIGHT;
  const horizontalSpan = Math.max(points.length - 1, 4);
  let stepPath = `M ${LEFT} ${chartY(points[0]?.remaining_pieces ?? target, maximum)}`;

  for (let index = 1; index < points.length; index += 1) {
    const x = LEFT + (index / horizontalSpan) * innerWidth;
    const y = chartY(points[index].remaining_pieces, maximum);
    stepPath += ` H ${x} V ${y}`;
  }

  const lastX = LEFT + ((points.length - 1) / horizontalSpan) * innerWidth;
  const remaining = points.at(-1)?.remaining_pieces ?? target;

  return (
    <>
      <svg className="production-chart" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Remaining target pieces decreasing after each completed garment">
        <Grid maximum={maximum} />
        <path d={stepPath} className="target-step-line" />
        {points.map((point, index) => {
          const x = LEFT + (index / horizontalSpan) * innerWidth;
          const y = chartY(point.remaining_pieces, maximum);
          return (
            <g key={`${point.piece_number}-${index}`}>
              <circle cx={x} cy={y} r={4} className="target-step-marker" />
              {(points.length < 13 || index % Math.ceil(points.length / 10) === 0) ? (
                <text x={x} y={HEIGHT - 13} textAnchor="middle" className="chart-axis-label">{point.piece_number}</text>
              ) : null}
              <title>{`${point.piece_number} completed · ${point.remaining_pieces} remaining`}</title>
            </g>
          );
        })}
        <circle cx={lastX} cy={chartY(remaining, maximum)} r={6} className="target-step-final" />
      </svg>
      <div className="chart-footer"><span>Target {formatNumber(target)} pieces</span><strong>{formatNumber(remaining)} remaining</strong></div>
    </>
  );
}
