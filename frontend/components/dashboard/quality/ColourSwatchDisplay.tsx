// components/dashboard/quality/ColourSwatchDisplay.tsx
"use client";
import { useQualityStore } from "@/store/qualityStore";

export function ColourSwatchDisplay() {
  const { currentGarment } = useQualityStore();
  const colours = currentGarment?.colourDetections ?? [];

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
          Detected Colours
        </span>
        <span className="font-mono text-dim" style={{ fontSize: 9 }}>F3</span>
      </div>

      {/* Body */}
      <div style={{ padding: "16px 18px", flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
        {colours.length === 0 ? (
          <div
            className="flex items-center justify-center font-mono text-dim"
            style={{ flex: 1, fontSize: 11 }}
          >
            No garment detected
          </div>
        ) : (
          colours.map((c, i) => (
            <div key={c.id || i} className="flex items-center gap-3">
              {/* Colour swatch */}
              <div
                className="rounded-full shrink-0"
                style={{
                  width: 26, height: 26,
                  background: c.hex,
                  border: "1.5px solid rgba(255,255,255,0.14)",
                  boxShadow: `0 0 8px ${c.hex}55`,
                }}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between" style={{ marginBottom: 4 }}>
                  <span className="font-mono text-text-primary" style={{ fontSize: 11 }}>{c.name}</span>
                  <span className="font-mono text-text-muted" style={{ fontSize: 10 }}>
                    {c.percentage.toFixed(0)}%
                  </span>
                </div>
                <div className="rounded-full overflow-hidden" style={{ height: 3, background: "#243044" }}>
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${c.percentage}%`, background: c.hex, boxShadow: `0 0 4px ${c.hex}` }}
                  />
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}