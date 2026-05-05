// components/dashboard/quality/StyleLabelCard.tsx
"use client";
import { useQualityStore } from "@/store/qualityStore";

export function StyleLabelCard() {
  const { currentGarment } = useQualityStore();
  const s = currentGarment?.styleDetection;

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
          Style Recognition
        </span>
        <span className="font-mono text-dim" style={{ fontSize: 9 }}>F3</span>
      </div>

      {/* Body */}
      <div style={{ padding: "16px 18px", flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
        <div>
          <div className="font-mono text-dim uppercase" style={{ fontSize: 7.5, letterSpacing: "0.09em", marginBottom: 6 }}>
            Detected Style
          </div>
          <div className="font-display font-bold text-text-primary" style={{ fontSize: 22, lineHeight: 1 }}>
            {s?.style || "—"}
          </div>
        </div>

        {s && (
          <>
            {/* Confidence bar */}
            <div>
              <div className="flex items-center justify-between" style={{ marginBottom: 5 }}>
                <span className="font-mono text-dim" style={{ fontSize: 8 }}>Confidence</span>
                <span
                  className="font-mono font-semibold"
                  style={{ fontSize: 11, color: s.confidenceScore > 0.8 ? "#22C55E" : "#FACC15" }}
                >
                  {(s.confidenceScore * 100).toFixed(0)}%
                </span>
              </div>
              <div className="rounded-full overflow-hidden" style={{ height: 4, background: "#243044" }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${s.confidenceScore * 100}%`,
                    background: s.confidenceScore > 0.8 ? "#22C55E" : "#FACC15",
                  }}
                />
              </div>
            </div>

            {/* Alternative detection */}
            {s.alternativeStyle && (
              <div style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 7, padding: "10px 13px" }}>
                <div className="font-mono text-dim uppercase" style={{ fontSize: 7.5, letterSpacing: "0.09em", marginBottom: 4 }}>
                  Alt. Detection
                </div>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-text-muted" style={{ fontSize: 11 }}>
                    {s.alternativeStyle}
                  </span>
                  <span className="font-mono text-dim" style={{ fontSize: 10 }}>
                    {s.alternativeScore ? `${(s.alternativeScore * 100).toFixed(0)}%` : ""}
                  </span>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}