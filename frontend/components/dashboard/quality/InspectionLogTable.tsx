// components/dashboard/quality/InspectionLogTable.tsx
"use client";
import { useState } from "react";
import { useQualityStore } from "@/store/qualityStore";
import type { QualityDecision } from "@/lib/types";

const PAGE = 8;

const D_COLOR: Record<QualityDecision, string> = {
  PASS: "#22C55E", REWORK: "#FACC15", MISMATCH: "#EF4444",
};

export function InspectionLogTable() {
  const { inspectionLog } = useQualityStore();
  const [page, setPage] = useState(0);

  const totalPages = Math.ceil(inspectionLog.length / PAGE);
  const rows       = inspectionLog.slice(page * PAGE, (page + 1) * PAGE);

  return (
    <div
      className="overflow-hidden"
      style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 12 }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 shrink-0"
        style={{ height: 48, background: "#131B26", borderBottom: "1px solid #243044" }}
      >
        <span className="font-mono text-text-muted uppercase" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
          Inspection Log
        </span>
        <span className="font-mono text-dim" style={{ fontSize: 9 }}>
          {inspectionLog.length} records
        </span>
      </div>

      {/* Column headers */}
      <div
        className="grid font-mono text-dim uppercase"
        style={{
          fontSize: 8, letterSpacing: "0.1em",
          gridTemplateColumns: "76px 70px 44px 72px 1fr 78px",
          gap: "0 10px",
          borderBottom: "1px solid #243044",
          padding: "10px 20px",
        }}
      >
        <span>Time</span>
        <span>Spec</span>
        <span>Size</span>
        <span>Style</span>
        <span>Colour</span>
        <span>Decision</span>
      </div>

      {/* Rows */}
      <div className="overflow-y-auto" style={{ maxHeight: 264 }}>
        {rows.length === 0 && (
          <div className="flex items-center justify-center font-mono text-dim" style={{ height: 64, fontSize: 11 }}>
            No inspections yet
          </div>
        )}
        {rows.map((rec, i) => {
          const g      = rec.garmentAnalysis;
          const dColor = D_COLOR[rec.decision] ?? "#6B7A8D";
          return (
            <div
              key={rec.id}
              className="grid items-center font-mono"
              style={{
                gridTemplateColumns: "76px 70px 44px 72px 1fr 78px",
                gap: "0 10px",
                padding: "11px 20px",
                fontSize: 11,
                borderBottom: i < rows.length - 1 ? "1px solid rgba(36,48,68,0.3)" : "none",
                background: i === 0 && page === 0 ? `${dColor}08` : "transparent",
              }}
            >
              <span className="text-text-muted">
                {new Date(rec.timestamp).toLocaleTimeString([], {
                  hour: "2-digit", minute: "2-digit", second: "2-digit",
                })}
              </span>
              <span className="text-text-muted">{rec.specLabel}</span>
              <span className="font-semibold text-accent">{g.sizeMeasurement.detectedSize}</span>
              <span className="text-text-muted">{g.styleDetection.style}</span>
              <div className="flex items-center gap-1.5">
                {g.colourDetections.slice(0, 2).map((c, ci) => (
                  <div
                    key={ci}
                    className="rounded-full shrink-0"
                    style={{ width: 12, height: 12, background: c.hex, border: "1px solid rgba(255,255,255,0.1)" }}
                  />
                ))}
              </div>
              <div className="flex items-center gap-1.5">
                <div
                  className="rounded-full shrink-0"
                  style={{ width: 5, height: 5, background: dColor, boxShadow: `0 0 4px ${dColor}` }}
                />
                <span
                  className="font-bold"
                  style={{ fontSize: 8.5, letterSpacing: "0.06em", color: dColor }}
                >
                  {rec.decision}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-5 py-3" style={{ borderTop: "1px solid #243044" }}>
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="font-mono text-text-muted transition-colors hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            style={{ fontSize: 10, background: "none", border: "none" }}
          >
            ← Prev
          </button>
          <span className="font-mono text-dim" style={{ fontSize: 9 }}>
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="font-mono text-text-muted transition-colors hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            style={{ fontSize: 10, background: "none", border: "none" }}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}