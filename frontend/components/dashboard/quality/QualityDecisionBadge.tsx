"use client";

import { useQualityStore } from "@/store/qualityStore";
import type { QualityDecision } from "@/lib/types";

type BadgeConfig = {
  color: string;
  bg: string;
  border: string;
  icon: string;
  desc: string;
  glow: string;
};

const CFG: Record<QualityDecision | "none", BadgeConfig> = {
  PASS: {
    color: "#22C55E",
    bg: "rgba(34,197,94,0.1)",
    border: "rgba(34,197,94,0.35)",
    icon: "✓",
    desc: "Meets all specifications",
    glow: "0 0 24px rgba(34,197,94,0.2)",
  },
  REWORK: {
    color: "#FACC15",
    bg: "rgba(250,204,21,0.1)",
    border: "rgba(250,204,21,0.35)",
    icon: "↩",
    desc: "Size or quality issue",
    glow: "0 0 24px rgba(250,204,21,0.16)",
  },
  MISMATCH: {
    color: "#EF4444",
    bg: "rgba(239,68,68,0.1)",
    border: "rgba(239,68,68,0.35)",
    icon: "✗",
    desc: "Specification mismatch",
    glow: "0 0 24px rgba(239,68,68,0.18)",
  },
  none: {
    color: "#3A4A5C",
    bg: "rgba(255,255,255,0.02)",
    border: "#243044",
    icon: "?",
    desc: "Awaiting inspection",
    glow: "none",
  },
};

export function QualityDecisionBadge() {
  const { currentGarment } = useQualityStore();

  const decisionKey: QualityDecision | "none" = currentGarment?.decision ?? "none";
  const cfg = CFG[decisionKey];

  return (
    <div
      className="flex flex-col overflow-hidden transition-all duration-300"
      style={{
        background: "#1A2536",
        border: `1px solid ${cfg.border}`,
        borderRadius: 12,
        boxShadow: cfg.glow,
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 shrink-0"
        style={{
          height: 48,
          background: "#131B26",
          borderBottom: `1px solid ${cfg.border}`,
        }}
      >
        <span
          className="font-mono text-text-muted uppercase"
          style={{ fontSize: 9, letterSpacing: "0.14em" }}
        >
          Quality Decision
        </span>

        {decisionKey !== "none" && (
          <div
            className="rounded-full animate-pulse-slow"
            style={{
              width: 7,
              height: 7,
              background: cfg.color,
              boxShadow: `0 0 6px ${cfg.color}`,
            }}
          />
        )}
      </div>

      {/* Body */}
      <div
        style={{
          padding: "16px 18px",
          flex: 1,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {/* Big decision badge */}
        <div
          className="flex items-center gap-4 rounded-xl"
          style={{
            padding: "14px 16px",
            background: cfg.bg,
            border: `1px solid ${cfg.border}`,
          }}
        >
          <div
            className="flex items-center justify-center shrink-0 font-mono font-bold"
            style={{
              width: 40,
              height: 40,
              borderRadius: 10,
              background: `${cfg.color}20`,
              border: `1px solid ${cfg.color}40`,
              color: cfg.color,
              fontSize: 20,
              lineHeight: 1,
            }}
          >
            {cfg.icon}
          </div>

          <div>
            <div
              className="font-mono font-bold"
              style={{
                fontSize: 18,
                color: cfg.color,
                letterSpacing: "0.06em",
                lineHeight: 1,
              }}
            >
              {decisionKey === "none" ? "PENDING" : decisionKey}
            </div>

            <div
              className="font-mono text-text-muted"
              style={{ fontSize: 9, marginTop: 4 }}
            >
              {cfg.desc}
            </div>
          </div>
        </div>

        {/* Confidence stats */}
        {currentGarment && (
          <div className="grid grid-cols-2 gap-2">
            <div
              style={{
                background: "#0B1017",
                border: "1px solid #243044",
                borderRadius: 7,
                padding: "11px 13px",
              }}
            >
              <div
                className="font-mono text-dim uppercase"
                style={{
                  fontSize: 7.5,
                  letterSpacing: "0.09em",
                  marginBottom: 5,
                }}
              >
                Confidence
              </div>
              <div
                className="font-mono font-semibold"
                style={{ fontSize: 14, color: cfg.color }}
              >
                {(currentGarment.overallConfidence * 100).toFixed(0)}%
              </div>
            </div>

            <div
              style={{
                background: "#0B1017",
                border: "1px solid #243044",
                borderRadius: 7,
                padding: "11px 13px",
              }}
            >
              <div
                className="font-mono text-dim uppercase"
                style={{
                  fontSize: 7.5,
                  letterSpacing: "0.09em",
                  marginBottom: 5,
                }}
              >
                Matches
              </div>
              <div
                className="font-mono font-semibold text-text-primary"
                style={{ fontSize: 14 }}
              >
                {currentGarment.specMatchResults.filter((r) => r.isMatch).length}
                <span className="text-dim">/{currentGarment.specMatchResults.length}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}