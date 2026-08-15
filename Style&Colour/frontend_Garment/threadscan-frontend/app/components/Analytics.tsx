"use client";
import { Bar, Doughnut } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from "chart.js";
import { colorHex } from "./FabricSwatch"; // අපි කලින් හදපු පාට ලබාගන්නා ෆයිල් එක
import { BarChart3 } from "lucide-react";

// ChartJS සඳහා අවශ්‍ය කොටස් Register කිරීම
ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend, ArcElement);

export default function Analytics({ history }: { history: any[] }) {
  // 1. දත්ත වෙන් කරගැනීම (Aggregation)
  const styleCounts: Record<string, number> = {};
  const colorCounts: Record<string, number> = {};

  history.forEach((scan) => {
    // Style ගණනය කිරීම
    styleCounts[scan.style_name] = (styleCounts[scan.style_name] || 0) + 1;
    // පාට ගණනය කිරීම
    colorCounts[scan.main_color] = (colorCounts[scan.main_color] || 0) + 1;
  });

  // 2. Style Pie Chart එක සඳහා දත්ත
  const styleLabels = Object.keys(styleCounts);
  const styleData = Object.values(styleCounts);
  const styleColors = ["#3FE0A1", "#F5B24A", "#FF6B5E", "#3E6FD8", "#B98CE0", "#7C877F"];

  const styleChartData = {
    labels: styleLabels,
    datasets: [
      {
        data: styleData,
        backgroundColor: styleColors.slice(0, styleLabels.length),
        borderColor: "#111814", // Dark background color එක
        borderWidth: 2,
      },
    ],
  };

  // 3. Color Bar Chart එක සඳහා දත්ත
  const colorLabels = Object.keys(colorCounts);
  const colorData = Object.values(colorCounts);
  // අදාළ වර්ණයේ නමට ගැලපෙන නියම පාට ලබා ගැනීම
  const barColors = colorLabels.map((colorName) => colorHex(colorName));

  const colorChartData = {
    labels: colorLabels,
    datasets: [
      {
        label: "Pieces Scanned",
        data: colorData,
        backgroundColor: barColors,
        borderRadius: 4,
      },
    ],
  };

  // ප්‍රස්ථාර සඳහා පොදු Styling Option එක
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    color: "#8B9990", // Text color
    plugins: {
      legend: {
        position: "bottom" as const,
        labels: { font: { family: "'IBM Plex Mono', monospace", size: 10 } },
      },
    },
  };

  const barChartOptions = {
    ...chartOptions,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: false }, ticks: { font: { family: "'IBM Plex Mono', monospace", size: 10 } } },
      y: { grid: { color: "#1A2420" }, ticks: { font: { family: "'IBM Plex Mono', monospace", size: 10 }, stepSize: 1 } },
    },
  };

  return (
    <div className="flex flex-col gap-6 h-full">
      <div className="flex items-center gap-2 mb-2">
        <BarChart3 size={18} className="text-brandGreen" />
        <h2 className="text-xl font-bold text-textMain">Live Analytics</h2>
      </div>

      {history.length === 0 ? (
        <div className="flex-1 flex items-center justify-center border border-dashed border-borderStrong rounded-lg text-textFaint font-mono text-sm">
          No data available. Waiting for AI scans...
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[350px]">
          
          {/* Style Chart Panel */}
          <div className="bg-panel border border-borderStrong rounded-lg p-5 flex flex-col">
            <h3 className="text-textDim font-bold text-[11px] tracking-widest uppercase mb-4 border-b border-borderSoft pb-2">
              Production by Style
            </h3>
            <div className="flex-1 relative min-h-[250px]">
              <Doughnut data={styleChartData} options={{ ...chartOptions, cutout: "65%" }} />
            </div>
          </div>

          {/* Color Chart Panel */}
          <div className="bg-panel border border-borderStrong rounded-lg p-5 flex flex-col">
            <h3 className="text-textDim font-bold text-[11px] tracking-widest uppercase mb-4 border-b border-borderSoft pb-2">
              Production by Color
            </h3>
            <div className="flex-1 relative min-h-[250px]">
              <Bar data={colorChartData} options={barChartOptions} />
            </div>
          </div>

        </div>
      )}
    </div>
  );
}