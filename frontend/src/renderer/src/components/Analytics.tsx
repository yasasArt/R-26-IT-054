import { useEffect, useState } from "react";
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
} from "chart.js";
import { colorHex } from "./FabricSwatch";
import { BarChart3, TrendingUp, Target } from "lucide-react";
import {
  fetchDailyStats,
  fetchPrediction,
  DailyStat,
  PredictionResult,
  GarmentScan,
  DecisionSummary,
  CATEGORIES,
  CATEGORY_LABEL,
} from "../lib/api";

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend, ArcElement);

const CHART_CYCLE = "#5875F0";
const CHART_TARGET = "#22A27E";
const CHART_GRID = "#E9EDF4";
const CHART_AXIS = "#7B899E";
const DOUGHNUT_COLORS = ["#4F6DF5", "#22A27E", "#B97519", "#765AC9", "#BD4A67", "#8691A4"];
const CHART_PACKED = "#5875F0";
const CHART_REMAINING = "#E9EDF4";

export default function Analytics({ history, summary }: { history: GarmentScan[]; summary: DecisionSummary | null }) {
  const [dailyStats, setDailyStats] = useState<DailyStat[]>([]);
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [tomorrowLabel, setTomorrowLabel] = useState("");

  useEffect(() => {
    (async () => {
      const [daily, pred] = await Promise.all([fetchDailyStats(), fetchPrediction()]);
      setDailyStats(daily);
      setPrediction(pred);
      setTomorrowLabel(
        new Date(Date.now() + 86400000).toLocaleDateString(undefined, { month: "short", day: "numeric" })
      );
    })();
  }, []);

  const trendLabels = [
    ...dailyStats.map((d) => new Date(d.date).toLocaleDateString(undefined, { month: "short", day: "numeric" })),
    ...(prediction ? [`${tomorrowLabel} (forecast)`] : []),
  ];

  const trendChartData = {
    labels: trendLabels,
    datasets: [
      {
        label: "Actual Pieces Packed",
        data: [...dailyStats.map((d) => d.count), null],
        borderColor: CHART_CYCLE,
        backgroundColor: CHART_CYCLE,
        tension: 0.35,
        pointRadius: 4,
        pointBackgroundColor: CHART_CYCLE,
      },
      {
        label: "Predicted (Next Day)",
        data: [...dailyStats.map(() => null), prediction?.predicted_count ?? null],
        borderColor: CHART_TARGET,
        backgroundColor: CHART_TARGET,
        borderDash: [6, 4],
        pointRadius: 6,
      },
    ],
  };

  const styleCounts: Record<string, number> = {};
  const colorCounts: Record<string, number> = {};

  history.forEach((scan) => {
    styleCounts[scan.style_name] = (styleCounts[scan.style_name] || 0) + 1;
    colorCounts[scan.main_color] = (colorCounts[scan.main_color] || 0) + 1;
  });

  const styleLabels = Object.keys(styleCounts);
  const styleData = Object.values(styleCounts);
  // Raw style_name values ("SHIRT", "T_SHIRT"...) match the CATEGORY_LABEL
  // keys exactly, so the doughnut can show the same friendly names used
  // everywhere else instead of raw uppercase class names.
  const styleDisplayLabels = styleLabels.map((label) => CATEGORY_LABEL[label as keyof typeof CATEGORY_LABEL] ?? label);

  const styleChartData = {
    labels: styleDisplayLabels,
    datasets: [
      {
        data: styleData,
        backgroundColor: DOUGHNUT_COLORS.slice(0, styleLabels.length),
        borderColor: "#FFFFFF",
        borderWidth: 2,
      },
    ],
  };

  const categories = summary?.categories;
  const categoryPredictions = prediction?.categories;
  const categoryChartData = categories && {
    labels: CATEGORIES.map((c) => CATEGORY_LABEL[c]),
    datasets: [
      {
        label: "Packed",
        data: CATEGORIES.map((c) => categories[c].total_packed),
        backgroundColor: CHART_PACKED,
        borderRadius: 6,
      },
      {
        label: "Target",
        data: CATEGORIES.map((c) => categories[c].target_pieces),
        backgroundColor: CHART_REMAINING,
        borderRadius: 6,
      },
      // Projected total after tomorrow's forecasted output, not tomorrow's
      // count on its own - lets the bar be read directly against the same
      // Target bar (does the forecast get us there, or not).
      {
        label: "Projected After Tomorrow",
        data: CATEGORIES.map((c) => categories[c].total_packed + (categoryPredictions?.[c]?.predicted_count ?? 0)),
        backgroundColor: CHART_TARGET,
        borderRadius: 6,
      },
    ],
  };

  const colorLabels = Object.keys(colorCounts);
  const colorData = Object.values(colorCounts);
  const barColors = colorLabels.map((colorName) => colorHex(colorName));

  const colorChartData = {
    labels: colorLabels,
    datasets: [
      {
        label: "Pieces Scanned",
        data: colorData,
        backgroundColor: barColors,
        borderRadius: 6,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "bottom" as const,
        labels: { font: { family: "IBM Plex Mono, monospace", size: 10 }, color: CHART_AXIS },
      },
    },
  };

  const cartesianOptions = {
    ...chartOptions,
    scales: {
      x: { grid: { display: false }, ticks: { font: { family: "IBM Plex Mono, monospace", size: 10 }, color: CHART_AXIS } },
      y: {
        grid: { color: CHART_GRID },
        ticks: { font: { family: "IBM Plex Mono, monospace", size: 10 }, color: CHART_AXIS, stepSize: 1 },
      },
    },
  };

  return (
    <div className="flex flex-col gap-6 h-full">
      <div className="flex items-center gap-2 mb-2">
        <BarChart3 size={18} className="text-accent" />
        <h2 className="text-xl font-bold text-ink">Live Analytics</h2>
      </div>

      <div className="bg-surface border border-line rounded-xl p-5 flex flex-col h-[320px] shadow-sm">
        <div className="flex items-center justify-between mb-4 border-b border-line pb-3">
          <h3 className="text-ink-secondary font-semibold text-[11px] tracking-widest uppercase flex items-center gap-2">
            <TrendingUp size={14} className="text-chart-target" /> Daily Output &amp; Next-Day Forecast
          </h3>
          {prediction && (
            <span className="font-mono text-[10px] text-ink-secondary bg-success-soft text-success px-2 py-1 rounded-full">
              Predicted tomorrow: {prediction.predicted_count} pcs ({prediction.method.replaceAll("_", " ")}, {prediction.days_used}d history)
            </span>
          )}
        </div>
        {dailyStats.length === 0 ? (
          <div className="flex-1 flex items-center justify-center text-ink-soft font-mono text-sm">
            No daily history yet. Waiting for scans...
          </div>
        ) : (
          <div className="flex-1 relative min-h-[220px]">
            <Line data={trendChartData} options={cartesianOptions} />
          </div>
        )}
      </div>

      {categoryChartData && (
        <div className="bg-surface border border-line rounded-xl p-5 flex flex-col h-[320px] shadow-sm">
          <h3 className="text-ink-secondary font-semibold text-[11px] tracking-widest uppercase mb-4 border-b border-line pb-3 flex items-center gap-2">
            <Target size={14} className="text-accent" /> Category Target Progress &amp; Next-Day Forecast
          </h3>
          <div className="flex-1 relative min-h-[220px]">
            <Bar data={categoryChartData} options={cartesianOptions} />
          </div>
        </div>
      )}

      {history.length === 0 ? (
        <div className="flex-1 flex items-center justify-center border border-dashed border-line rounded-xl text-ink-soft font-mono text-sm py-10">
          No data available. Waiting for AI scans...
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[350px]">
          <div className="bg-surface border border-line rounded-xl p-5 flex flex-col shadow-sm">
            <h3 className="text-ink-secondary font-semibold text-[11px] tracking-widest uppercase mb-4 border-b border-line pb-2">
              Production by Style
            </h3>
            <div className="flex-1 relative min-h-[250px]">
              <Doughnut data={styleChartData} options={{ ...chartOptions, cutout: "65%" }} />
            </div>
          </div>

          <div className="bg-surface border border-line rounded-xl p-5 flex flex-col shadow-sm">
            <h3 className="text-ink-secondary font-semibold text-[11px] tracking-widest uppercase mb-4 border-b border-line pb-2">
              Production by Color
            </h3>
            <div className="flex-1 relative min-h-[250px]">
              <Bar data={colorChartData} options={{ ...cartesianOptions, plugins: { legend: { display: false } } }} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
