// components/ui/Badge.tsx
import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

export type BadgeVariant =
  | "default"
  | "success"
  | "warning"
  | "danger"
  | "accent"
  | "orange"
  | "dim";

export type BadgeSize = "xs" | "sm" | "md";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  pulse?: boolean;
}

const variantMap: Record<BadgeVariant, { wrap: string; dot: string }> = {
  default: { wrap: "bg-card border-card-border text-text-muted",     dot: "bg-text-muted" },
  success: { wrap: "bg-success/10 border-success/25 text-success",   dot: "bg-success" },
  warning: { wrap: "bg-warning/10 border-warning/25 text-warning",   dot: "bg-warning" },
  danger:  { wrap: "bg-danger/10 border-danger/25 text-danger",      dot: "bg-danger" },
  accent:  { wrap: "bg-accent/10 border-accent/25 text-accent",      dot: "bg-accent" },
  orange:  { wrap: "bg-orange/10 border-orange/25 text-orange",      dot: "bg-orange" },
  dim:     { wrap: "bg-dim/20 border-dim/30 text-text-muted",        dot: "bg-dim" },
};

const sizeMap: Record<BadgeSize, string> = {
  xs: "px-1.5 py-px text-[9px] gap-1",
  sm: "px-2 py-0.5 text-[10px] gap-1.5",
  md: "px-2.5 py-1 text-xs gap-1.5",
};

export function Badge({
  variant = "default",
  size = "sm",
  dot = false,
  pulse = false,
  className,
  children,
  ...props
}: BadgeProps) {
  const cfg = variantMap[variant];
  return (
    <span
      className={cn(
        "inline-flex items-center border rounded-badge font-mono font-semibold uppercase tracking-wide whitespace-nowrap",
        cfg.wrap,
        sizeMap[size],
        className
      )}
      {...props}
    >
      {dot && (
        <span
          className={cn(
            "rounded-full shrink-0",
            size === "xs" ? "w-1 h-1" : "w-1.5 h-1.5",
            cfg.dot,
            pulse && "animate-pulse-slow"
          )}
        />
      )}
      {children}
    </span>
  );
}