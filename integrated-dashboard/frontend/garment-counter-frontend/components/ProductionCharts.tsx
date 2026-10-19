import { buildCycleChartData } from "@platform/shared/chart-data";
import type { PieceEvent } from "@platform/shared/types";
import { formatNumber } from "../lib/format";
import { EmptyState } from "./OperatorUi";

const WIDTH = 940;
const HEIGHT = 270;
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

export function CycleTimeChart({
  events,
  estimatedCycleTime,
}: {
  events: PieceEvent[];
  estimatedCycleTime: number | null;
}) {
  const data = buildCycleChartData(events);

  if (!data.length) {
    return <EmptyState icon="clock" title="Waiting for the first garment" description="The first completed piece and every piece after it will appear here with a measured cycle time." />;
  }

  const maximum = Math.max(
    ...data.map((point) => point.cycleSeconds),
    estimatedCycleTime ?? 0,
    1,
  ) * 1.18;
  const innerWidth = WIDTH - LEFT - RIGHT;
  const slotWidth = innerWidth / data.length;
  const barWidth = Math.min(42, Math.max(8, slotWidth - 9));
  const average = data.reduce((sum, point) => sum + point.cycleSeconds, 0) / data.length;

  return (
    <>
      <svg className="production-chart cycle-chart" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Cycle time in seconds for every completed garment">
        <Grid maximum={maximum} />
        {estimatedCycleTime !== null ? (
          <g>
            <line
              x1={LEFT}
              x2={WIDTH - RIGHT}
              y1={chartY(estimatedCycleTime, maximum)}
              y2={chartY(estimatedCycleTime, maximum)}
              className="cycle-estimate-line"
            />
            <text
              x={WIDTH - RIGHT}
              y={chartY(estimatedCycleTime, maximum) - 6}
              textAnchor="end"
              className="cycle-estimate-label"
            >
              Estimate {formatNumber(estimatedCycleTime, 1)}s
            </text>
          </g>
        ) : null}
        {data.map((point, index) => {
          const x = LEFT + slotWidth * index + (slotWidth - barWidth) / 2;
          const y = chartY(point.cycleSeconds, maximum);
          return (
            <g key={point.pieceNumber}>
              <rect
                x={x}
                y={y}
                width={barWidth}
                height={HEIGHT - BOTTOM - y}
                rx={5}
                className={
                  estimatedCycleTime === null
                    ? "cycle-bar"
                    : point.cycleSeconds <= estimatedCycleTime
                      ? "cycle-bar cycle-bar-within"
                      : "cycle-bar cycle-bar-over"
                }
              />
              {(data.length < 13 || index % Math.ceil(data.length / 10) === 0) ? (
                <text x={x + barWidth / 2} y={HEIGHT - 13} textAnchor="middle" className="chart-axis-label">{point.label}</text>
              ) : null}
              <title>{`Piece ${point.pieceNumber}: ${formatNumber(point.cycleSeconds, 2)} seconds`}</title>
            </g>
          );
        })}
      </svg>
      <div className="chart-footer">
        <span className="cycle-chart-legend">
          {estimatedCycleTime === null ? "Includes piece #1" : (
            <><i className="legend-within" /> Within estimate <i className="legend-over" /> Over estimate</>
          )}
        </span>
        <strong>Average {formatNumber(average, 1)} sec</strong>
      </div>
    </>
  );
}
