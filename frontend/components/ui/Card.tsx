// components/ui/Card.tsx
import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

type CardVariant  = "default" | "surface" | "elevated";
type CardPadding  = "none" | "sm" | "md" | "lg";
type CardGlow     = "none" | "green" | "blue" | "red" | "yellow" | "orange";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant;
  padding?: CardPadding;
  glow?: CardGlow;
  interactive?: boolean;
}

const variantMap: Record<CardVariant, string> = {
  default:  "bg-card border-card-border",
  surface:  "bg-surface border-card-border",
  elevated: "bg-card border-card-border shadow-card",
};

const paddingMap: Record<CardPadding, string> = {
  none: "",
  sm:   "p-3",
  md:   "p-4",
  lg:   "p-5",
};

const glowMap: Record<CardGlow, string> = {
  none:   "",
  green:  "border-success/30 shadow-glow-green",
  blue:   "border-accent/30 shadow-glow-blue",
  red:    "border-danger/30 shadow-glow-red",
  yellow: "border-warning/30 shadow-glow-yellow",
  orange: "border-orange/30",
};

export function Card({
  variant = "default",
  padding = "md",
  glow = "none",
  interactive = false,
  className,
  children,
  ...props
}: CardProps) {
  return (
    <div
      className={cn(
        "rounded-card border transition-colors duration-200",
        variantMap[variant],
        paddingMap[padding],
        glowMap[glow],
        interactive && "hover:border-accent/30 cursor-pointer",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex items-center justify-between mb-3", className)}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardTitle({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn(
        "text-[11px] font-mono uppercase tracking-widest text-text-muted",
        className
      )}
      {...props}
    >
      {children}
    </h3>
  );
}

export function CardDivider({ className }: { className?: string }) {
  return <div className={cn("h-px bg-card-border my-4", className)} />;
}