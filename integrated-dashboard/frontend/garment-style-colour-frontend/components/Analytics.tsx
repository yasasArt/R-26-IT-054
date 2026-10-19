import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Bar, Doughnut, Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  type ChartOptions,
  type TooltipItem,
} from "chart.js";
import { colorHex } from "./FabricSwatch";
import { BarChart3, TrendingUp, Target, Palette, PieChart } from "lucide-react";
import {
  fetchDailyStats,
  fetchPrediction,
  DailyStat,
  PredictionResult,
  GarmentScan,
  DecisionSummary,
  GarmentCategory,
  CATEGORIES,
  CATEGORY_LABEL,
} from "../lib/api";

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend, ArcElement);

// Series colours. Validated with the dataviz palette checker (lightness band,
// chroma, colour-blind separation and contrast on the white card surface).
const CHART_ACTUAL = "#5875F0";
const CHART_FORECAST = "#22A27E";
const CHART_PACKED = "#4F6DF5";
const CHART_TARGET = "#B97519";
const CHART_PROJECTED = "#22A27E";
const CHART_GRID = "#E9EDF4";
const CHART_AXIS = "#7B899E";
const CHART_TITLE = "#5B6980";

// One fixed colour per garment style, so a style keeps its colour no matter
// which styles happen to appear in the data or in which order.
const STYLE_COLOURS: Record<GarmentCategory, string> = {
  SHIRT: "#4F6DF5",
  T_SHIRT: "#22A27E",
  TROUSER: "#B97519",
  SHORT: "#765AC9",
};
const OTHER_STYLE_COLOUR = "#8691A4";

const MONO = { family: "IBM Plex Mono, monospace", size: 10 };
const MONO_LARGE = { family: "IBM Plex Mono, monospace", size: 12 };
const AXIS_TITLE_FONT = { family: "Inter, system-ui, sans-serif", size: 11, weight: 600 as const };
const AXIS_TITLE_FONT_LARGE = { family: "Inter, system-ui, sans-serif", size: 13, weight: 600 as const };

function axisTitle(text: string, font = AXIS_TITLE_FONT) {
  return { display: true, text, color: CHART_TITLE, font, padding: { top: 6, bottom: 2 } };
}

// Shared X/Y axes for every "number of garments" chart: a named category
// axis and a whole-piece count axis that always starts at zero.
function countAxes(xTitle: string, yTitle: string) {
  return {
    x: {
      grid: { display: false },
      ticks: { font: MONO, color: CHART_AXIS },
      title: axisTitle(xTitle),
    },
    y: {
      beginAtZero: true,
      grid: { color: CHART_GRID },
      border: { display: false },
      // Whole pieces only, with automatic spacing (stepSize: 1 drew one
      // gridline per piece, i.e. hundreds of lines once targets are large).
      ticks: { font: MONO, color: CHART_AXIS, precision: 0 },
      title: axisTitle(yTitle),
    },
  };
}

const legendBottom = {
  position: "bottom" as const,
  labels: { font: MONO, color: CHART_AXIS, boxWidth: 12, boxHeight: 12, useBorderRadius: true, borderRadius: 3 },
};

function pcs(value: number | null | undefined) {
  return `${(value ?? 0).toLocaleString()} pcs`;
}

function styleLabel(style: string) {
  return CATEGORY_LABEL[style as GarmentCategory] ?? style;
}

function ChartCard({
  icon,
  title,
  caption,
  children,
  height = "h-[340px]",
  badge,
}: {
  icon: ReactNode;
  title: string;
  caption: string;
  children: ReactNode;
  height?: string;
  badge?: ReactNode;
}) {
  return (
    <div className={`bg-surface border border-line rounded-xl p-5 flex flex-col ${height} shadow-sm`}>
      <div className="flex items-start justify-between gap-3 mb-3 border-b border-line pb-3">
        <div>
          <h3 className="text-ink-secondary font-semibold text-[11px] tracking-widest uppercase flex items-center gap-2">
            {icon} {title}
          </h3>
          <p className="text-ink-soft text-[11px] mt-1">{caption}</p>
        </div>
        {badge}
      </div>
      <div className="flex-1 relative min-h-0">{children}</div>
    </div>
  );
}

export default function Analytics({ history, summary }: { history: GarmentScan[]; summary: DecisionSummary | null }) {
  const [dailyStats, setDailyStats] = useState<DailyStat[]>([]);
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);

  // Re-fetch the server-side daily counts and forecast whenever a new garment
  // is captured, so the charts never go stale while the Analytics page is open.
  const historyKey = `${history.length}:${history[0]?._id ?? ""}`;
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [daily, pred] = await Promise.all([fetchDailyStats(), fetchPrediction()]);
      if (cancelled) return;
      setDailyStats(daily);
      setPrediction(pred);
    })();
    return () => {
      cancelled = true;
    };
  }, [historyKey]);

  const tomorrowLabel = new Date(Date.now() + 86400000).toLocaleDateString(undefined, { month: "short", day: "numeric" });

  // ---- Daily output & forecast (line) -----------------------------------
  const trendLabels = [
    ...dailyStats.map((d) => new Date(`${d.date}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })),
    ...(prediction ? [`${tomorrowLabel} (forecast)`] : []),
  ];
  const lastIndex = trendLabels.length - 1;
  const trendChartData = {
    labels: trendLabels,
    datasets: [
      {
        label: "Actual pieces packed",
        data: [...dailyStats.map((d) => d.count), ...(prediction ? [null] : [])],
        borderColor: CHART_ACTUAL,
        backgroundColor: CHART_ACTUAL,
        borderWidth: 3,
        tension: 0.35,
        pointRadius: 5,
        pointHoverRadius: 8,
        pointBackgroundColor: CHART_ACTUAL,
      },
      {
        label: "Forecast (next day)",
        // Starts from the last real day so the dashed segment visibly continues the trend.
        data: [
          ...dailyStats.map((d, index) => (prediction && index === dailyStats.length - 1 ? d.count : null)),
          ...(prediction ? [prediction.predicted_count] : []),
        ],
        borderColor: CHART_FORECAST,
        backgroundColor: CHART_FORECAST,
        borderWidth: 3,
        borderDash: [8, 5],
        pointRadius: trendLabels.map((_, index) => (index === lastIndex ? 8 : 0)),
        pointHoverRadius: 9,
      },
    ],
  };
  const trendOptions: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    layout: { padding: { top: 8, right: 12 } },
    plugins: {
      // Round legend markers: a dashed series draws a broken square swatch.
      legend: { ...legendBottom, labels: { ...legendBottom.labels, font: MONO_LARGE, padding: 18, usePointStyle: true, pointStyle: "circle" } },
      tooltip: {
        titleFont: { size: 13 },
        bodyFont: { size: 13 },
        padding: 10,
        filter: (item: TooltipItem<"line">) => item.parsed.y != null && !(item.datasetIndex === 1 && item.dataIndex !== lastIndex),
        callbacks: {
          label: (item: TooltipItem<"line">) => `${item.dataset.label}: ${pcs(item.parsed.y)}`,
        },
      },
    },
    // Same axes as the other count charts, with larger text and 10 % headroom
    // so the highest day and the forecast point are never clipped.
    scales: {
      x: {
        grid: { display: false },
        ticks: { font: MONO_LARGE, color: CHART_AXIS, maxRotation: 0, autoSkipPadding: 16 },
        title: axisTitle("Production date", AXIS_TITLE_FONT_LARGE),
      },
      y: {
        beginAtZero: true,
        grace: "10%",
        grid: { color: CHART_GRID },
        border: { display: false },
        ticks: { font: MONO_LARGE, color: CHART_AXIS, precision: 0 },
        title: axisTitle("Garments packed (pcs)", AXIS_TITLE_FONT_LARGE),
      },
    },
  };

  // ---- Per-style and per-colour counts (from capture history) -----------
  const stats = useMemo(() => {
    const styleCounts: Record<string, number> = {};
    const colorCounts: Record<string, number> = {};
    history.forEach((scan) => {
      styleCounts[scan.style_name] = (styleCounts[scan.style_name] || 0) + 1;
      colorCounts[scan.main_color] = (colorCounts[scan.main_color] || 0) + 1;
    });
    return { styleCounts, colorCounts };
  }, [history]);

  const totalScans = history.length;
  const orderedKeys = (record: Record<string, unknown>) => [
    ...CATEGORIES.filter((c) => record[c] !== undefined),
    ...Object.keys(record).filter((k) => !CATEGORIES.includes(k as GarmentCategory)),
  ];

  const styleKeys = orderedKeys(stats.styleCounts);
  const styleChartData = {
    labels: styleKeys.map(styleLabel),
    datasets: [
      {
        data: styleKeys.map((k) => stats.styleCounts[k]),
        backgroundColor: styleKeys.map((k) => STYLE_COLOURS[k as GarmentCategory] ?? OTHER_STYLE_COLOUR),
        borderColor: "#FFFFFF",
        borderWidth: 2,
        hoverOffset: 4,
      },
    ],
  };
  const doughnutOptions: ChartOptions<"doughnut"> = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "65%",
    plugins: {
      legend: legendBottom,
      tooltip: {
        callbacks: {
          label: (item: TooltipItem<"doughnut">) => {
            const value = Number(item.parsed);
            return `${item.label}: ${pcs(value)} (${totalScans ? ((value / totalScans) * 100).toFixed(1) : 0}%)`;
          },
        },
      },
    },
  };

  // ---- Category target progress (grouped bars) ---------------------------
  const categories = summary?.categories;
  const categoryPredictions = prediction?.categories;
  const roundedBar = { borderRadius: 4, borderSkipped: "start" as const };
  const categoryChartData = categories && {
    labels: CATEGORIES.map((c) => CATEGORY_LABEL[c]),
    datasets: [
      {
        label: "Packed",
        data: CATEGORIES.map((c) => categories[c].total_packed),
        backgroundColor: CHART_PACKED,
        ...roundedBar,
      },
      {
        label: "Target",
        data: CATEGORIES.map((c) => categories[c].target_pieces),
        backgroundColor: CHART_TARGET,
        ...roundedBar,
      },
      // Projected total after tomorrow's forecasted output, not tomorrow's
      // count on its own - lets the bar be read directly against the same
      // Target bar (does the forecast get us there, or not).
      {
        label: "Projected after tomorrow",
        data: CATEGORIES.map((c) => categories[c].total_packed + (categoryPredictions?.[c]?.predicted_count ?? 0)),
        backgroundColor: CHART_PROJECTED,
        ...roundedBar,
      },
    ],
  };
  const categoryOptions: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    datasets: { bar: { categoryPercentage: 0.7, barPercentage: 0.9 } },
    plugins: {
      legend: legendBottom,
      tooltip: { callbacks: { label: (item: TooltipItem<"bar">) => `${item.dataset.label}: ${pcs(item.parsed.y)}` } },
    },
    scales: countAxes("Garment style", "Pieces (pcs)"),
  };

  // ---- Production by colour (bars in the garment's own colour) -----------
  const colorEntries = Object.entries(stats.colorCounts).sort((a, b) => b[1] - a[1]);
  const colorChartData = {
    labels: colorEntries.map(([name]) => name),
    datasets: [
      {
        label: "Garments",
        data: colorEntries.map(([, count]) => count),
        backgroundColor: colorEntries.map(([name]) => colorHex(name)),
        // White/beige/yellow bars would vanish on the white card without an outline.
        borderColor: colorEntries.map(([name]) => (["WHITE", "BEIGE", "YELLOW"].includes(name.toUpperCase()) ? "#B3BFD1" : "transparent")),
        borderWidth: 1,
        ...roundedBar,
      },
    ],
  };
  const colorOptions: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (item: TooltipItem<"bar">) =>
            `${pcs(item.parsed.y)} (${totalScans ? ((item.parsed.y / totalScans) * 100).toFixed(1) : 0}% of all scans)`,
        },
      },
    },
    scales: countAxes("Main colour", "Garments scanned (pcs)"),
  };

  return (
    <div className="flex flex-col gap-6 h-full">
      <div className="flex items-center gap-2 mb-2">
        <BarChart3 size={18} className="text-accent" />
        <h2 className="text-xl font-bold text-ink">Live Analytics</h2>
      </div>

      <ChartCard
        icon={<TrendingUp size={14} className="text-chart-target" />}
        title="Daily Output & Next-Day Forecast"
        caption="Garments captured per day; the dashed point is tomorrow's forecast."
        height="h-[480px]"
        badge={
          prediction ? (
            <span className="font-mono text-[10px] bg-success-soft text-success px-2 py-1 rounded-full whitespace-nowrap">
              Predicted tomorrow: {prediction.predicted_count} pcs ({prediction.method.replaceAll("_", " ")}, {prediction.days_used}d history)
            </span>
          ) : null
        }
      >
        {dailyStats.length === 0 ? (
          <div className="h-full flex items-center justify-center text-ink-soft font-mono text-sm">No daily history yet. Waiting for scans...</div>
        ) : (
          <Line data={trendChartData} options={trendOptions} />
        )}
      </ChartCard>

      {categoryChartData && (
        <ChartCard
          icon={<Target size={14} className="text-accent" />}
          title="Category Target Progress & Next-Day Forecast"
          caption="For each style: pieces packed so far, the target, and the total expected after tomorrow."
        >
          <Bar data={categoryChartData} options={categoryOptions} />
        </ChartCard>
      )}

      {history.length === 0 ? (
        <div className="flex-1 flex items-center justify-center border border-dashed border-line rounded-xl text-ink-soft font-mono text-sm py-10">
          No data available. Waiting for AI scans...
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ChartCard
            icon={<PieChart size={14} className="text-accent" />}
            title="Production by Style"
            caption={`Share of all ${totalScans.toLocaleString()} captured garments.`}
            height="h-[360px]"
          >
            <Doughnut data={styleChartData} options={doughnutOptions} />
          </ChartCard>

          <ChartCard
            icon={<Palette size={14} className="text-accent" />}
            title="Production by Colour"
            caption="Garments per detected main colour, most common first."
            height="h-[360px]"
          >
            <Bar data={colorChartData} options={colorOptions} />
          </ChartCard>
        </div>
      )}
    </div>
  );
}
