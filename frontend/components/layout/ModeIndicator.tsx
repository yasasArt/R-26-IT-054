// components/layout/ModeIndicator.tsx
import { cn } from "@/lib/utils";
import type { AreaMode } from "@/lib/types";

interface ModeIndicatorProps {
  mode: AreaMode;
  size?: "xs" | "sm" | "md" | "lg";
  className?: string;
}

const modeCfg = {
  sewing: {
    label:      "Sewing Operator Area",
    shortLabel: "Sewing",
    dot:        "bg-success shadow-glow-green",
    text:       "text-success",
    border:     "bg-success/10 border-success/25",
  },
  quality: {
    label:      "Quality Checker Area",
    shortLabel: "Quality",
    dot:        "bg-accent shadow-glow-blue",
    text:       "text-accent",
    border:     "bg-accent/10 border-accent/25",
  },
};

const sizeCfg = {
  xs: { wrap: "px-2 py-0.5 text-[9px] gap-1",   dot: "w-1.5 h-1.5" },
  sm: { wrap: "px-2.5 py-1 text-[10px] gap-1.5", dot: "w-1.5 h-1.5" },
  md: { wrap: "px-3 py-1 text-xs gap-2",         dot: "w-2 h-2" },
  lg: { wrap: "px-4 py-1.5 text-sm gap-2",       dot: "w-2.5 h-2.5" },
};

export function ModeIndicator({
  mode,
  size = "md",
  className,
}: ModeIndicatorProps) {
  const m = modeCfg[mode];
  const s = sizeCfg[size];

  return (
    <span
      className={cn(
        "inline-flex items-center border rounded-badge font-mono font-bold uppercase tracking-widest whitespace-nowrap",
        m.border,
        m.text,
        s.wrap,
        className
      )}
    >
      <span
        className={cn(
          "rounded-full shrink-0 animate-pulse-slow",
          m.dot,
          s.dot
        )}
      />
      {size === "xs" || size === "sm" ? m.shortLabel : m.label}
    </span>
  );
}