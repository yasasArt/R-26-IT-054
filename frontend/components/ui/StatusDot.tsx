// components/ui/StatusDot.tsx
import { cn } from "@/lib/utils";

export type DotStatus =
  | "live"
  | "disconnected"
  | "error"
  | "warning"
  | "calibrating"
  | "idle";

export interface StatusDotProps {
  status: DotStatus;
  label?: string;
  size?: "xs" | "sm" | "md" | "lg";
  showLabel?: boolean;
  className?: string;
}

const dotCfg: Record<
  DotStatus,
  { color: string; glow: string; pulse: boolean; defaultLabel: string }
> = {
  live:         { color: "bg-success",    glow: "shadow-glow-green",  pulse: true,  defaultLabel: "Live" },
  disconnected: { color: "bg-danger",     glow: "shadow-glow-red",    pulse: false, defaultLabel: "Disconnected" },
  error:        { color: "bg-danger",     glow: "shadow-glow-red",    pulse: false, defaultLabel: "Error" },
  warning:      { color: "bg-warning",    glow: "shadow-glow-yellow", pulse: true,  defaultLabel: "Warning" },
  calibrating:  { color: "bg-warning",    glow: "shadow-glow-yellow", pulse: true,  defaultLabel: "Calibrating" },
  idle:         { color: "bg-text-muted", glow: "",                   pulse: false, defaultLabel: "Idle" },
};

const sizePx: Record<string, string> = {
  xs: "w-1.5 h-1.5",
  sm: "w-2 h-2",
  md: "w-2.5 h-2.5",
  lg: "w-3 h-3",
};

export function StatusDot({
  status,
  label,
  size = "md",
  showLabel = false,
  className,
}: StatusDotProps) {
  const cfg = dotCfg[status];
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span
        className={cn(
          "rounded-full shrink-0 block",
          sizePx[size],
          cfg.color,
          cfg.glow,
          cfg.pulse && "animate-pulse-slow"
        )}
      />
      {showLabel && (
        <span className="text-xs font-mono text-text-muted">
          {label ?? cfg.defaultLabel}
        </span>
      )}
    </span>
  );
}