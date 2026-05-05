// components/dashboard/quality/SizeResultCard.tsx
"use client";
import { useQualityStore } from "@/store/qualityStore";

const SIZE_COLOR: Record<string, string> = {
  S: "#3B82F6", M: "#22C55E", L: "#FACC15", XL: "#F97316", Unknown: "#3A4A5C",
};

export function SizeResultCard() {
  const { currentGarment } = useQualityStore();
  const m = currentGarment?.sizeMeasurement;
  const sizeColor = m ? (SIZE_COLOR[m.detectedSize] ?? "#3A4A5C") : "#3A4A5C";

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 12 }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 shrink-0"
        style={{ height: 48, background: "#131B26", borderBottom: "1px solid #243044" }}
      >
        <span className="font-mono text-text-muted uppercase" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
          Size Measurement
        </span>
        <span className="font-mono text-dim" style={{ fontSize: 9 }}>F4</span>
      </div>

      {/* Body */}
      <div style={{ padding: "16px 18px", flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
        {/* Big size label */}
        <div className="flex items-end justify-between">
          <div>
            <div className="font-mono text-dim uppercase" style={{ fontSize: 7.5, letterSpacing: "0.09em", marginBottom: 4 }}>
              Detected Size
            </div>
            <div
              className="font-mono font-bold"
              style={{ fontSize: 46, lineHeight: 1, color: sizeColor, letterSpacing: "-0.02em" }}
            >
              {m?.detectedSize || "—"}
            </div>
          </div>
          {m && (
            <div className="text-right">
              <div className="font-mono text-dim" style={{ fontSize: 7.5, marginBottom: 4 }}>Confidence</div>
              <div
                className="font-mono font-semibold"
                style={{ fontSize: 13, color: m.confidenceScore > 0.85 ? "#22C55E" : "#FACC15" }}
              >
                {(m.confidenceScore * 100).toFixed(0)}%
              </div>
            </div>
          )}
        </div>

        {/* Confidence bar */}
        {m && (
          <div className="rounded-full overflow-hidden" style={{ height: 4, background: "#243044" }}>
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${m.confidenceScore * 100}%`,
                background: m.confidenceScore > 0.85 ? "#22C55E" : "#FACC15",
              }}
            />
          </div>
        )}

        {/* Width + Height */}
        <div className="grid grid-cols-2 gap-2">
          <div style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 7, padding: "11px 13px" }}>
            <div className="font-mono text-dim uppercase" style={{ fontSize: 7.5, letterSpacing: "0.09em", marginBottom: 5 }}>Width</div>
            <div className="font-mono font-semibold text-warning" style={{ fontSize: 14 }}>
              {m ? `${m.widthCm.toFixed(1)} cm` : "—"}
            </div>
          </div>
          <div style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 7, padding: "11px 13px" }}>
            <div className="font-mono text-dim uppercase" style={{ fontSize: 7.5, letterSpacing: "0.09em", marginBottom: 5 }}>Height</div>
            <div className="font-mono font-semibold text-accent" style={{ fontSize: 14 }}>
              {m ? `${m.heightCm.toFixed(1)} cm` : "—"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}