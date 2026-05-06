// components/dashboard/quality/SpecMatchTable.tsx
"use client";
import { useQualityStore } from "@/store/qualityStore";

export function SpecMatchTable() {
  const { currentGarment, activeSpec } = useQualityStore();
  const results = currentGarment?.specMatchResults ?? [];
  const matchCount = results.filter(r => r.isMatch).length;

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{ background: "var(--card)", border: "1px solid var(--card-border)", borderRadius: 12 }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 shrink-0"
        style={{ height: 48, background: "var(--surface)", borderBottom: "1px solid var(--card-border)" }}
      >
        <div className="flex items-center gap-3">
          <span className="font-mono text-text-muted uppercase" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
            Specification Match
          </span>
          {results.length > 0 && (
            <span
              className="font-mono font-bold"
              style={{
                fontSize: 9, padding: "2px 8px", borderRadius: 4,
                background: matchCount === results.length ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
                border: `1px solid ${matchCount === results.length ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
                color: matchCount === results.length ? "#22C55E" : "#EF4444",
              }}
            >
              {matchCount}/{results.length} matched
            </span>
          )}
        </div>
        <span className="font-mono text-accent" style={{ fontSize: 10 }}>
          {activeSpec.specLabel}
        </span>
      </div>

      {/* Column headers */}
      <div
        className="grid font-mono text-dim uppercase"
        style={{
          fontSize: 8, letterSpacing: "0.1em",
          gridTemplateColumns: "1fr 1fr 1fr 38px",
          gap: "0 10px",
          borderBottom: "1px solid var(--card-border)",
          padding: "10px 20px",
        }}
      >
        <span>Attribute</span>
        <span>Expected</span>
        <span>Detected</span>
        <span></span>
      </div>

      {/* Rows */}
      <div className="overflow-y-auto" style={{ flex: 1 }}>
        {results.length === 0 ? (
          <div className="flex items-center justify-center font-mono text-dim" style={{ height: 80, fontSize: 11 }}>
            Awaiting inspection…
          </div>
        ) : (
          results.map((r, i) => (
            <div
              key={r.attribute}
              className="grid items-center font-mono"
              style={{
                gridTemplateColumns: "1fr 1fr 1fr 38px",
                gap: "0 10px",
                padding: "12px 20px",
                borderBottom: i < results.length - 1 ? "1px solid rgba(36,48,68,0.35)" : "none",
                background: !r.isMatch ? "rgba(239,68,68,0.03)" : "transparent",
              }}
            >
              <span className="text-text-muted capitalize" style={{ fontSize: 11 }}>{r.label}</span>
              <span className="text-text-muted" style={{ fontSize: 11 }}>{r.expected}</span>
              <span style={{ fontSize: 11, color: r.isMatch ? "var(--text)" : "#EF4444" }}>
                {r.detected}
              </span>
              <div
                className="flex items-center justify-center"
                style={{
                  width: 26, height: 26, borderRadius: 6,
                  background: r.isMatch ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
                  border: `1px solid ${r.isMatch ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
                }}
              >
                <span
                  className="font-mono font-bold"
                  style={{ fontSize: 11, color: r.isMatch ? "#22C55E" : "#EF4444" }}
                >
                  {r.isMatch ? "✓" : "✗"}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}