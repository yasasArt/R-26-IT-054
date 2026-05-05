// components/ui/Button.tsx
"use client";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "ghost"
  | "danger"
  | "success"
  | "warning"
  | "orange";

export type ButtonSize = "xs" | "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  fullWidth?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-accent hover:bg-accent/90 active:bg-accent/80 text-white border border-accent/60",
  secondary:
    "bg-card hover:bg-card-border active:bg-dim/30 text-text-primary border border-card-border hover:border-dim",
  ghost:
    "bg-transparent hover:bg-card active:bg-card-border text-text-muted hover:text-text-primary border border-transparent hover:border-card-border",
  danger:
    "bg-danger/10 hover:bg-danger/20 active:bg-danger/30 text-danger border border-danger/30 hover:border-danger/50",
  success:
    "bg-success/10 hover:bg-success/20 active:bg-success/30 text-success border border-success/30 hover:border-success/50",
  warning:
    "bg-warning/10 hover:bg-warning/20 active:bg-warning/30 text-warning border border-warning/30 hover:border-warning/50",
  orange:
    "bg-orange/10 hover:bg-orange/20 active:bg-orange/30 text-orange border border-orange/30 hover:border-orange/50",
};

const sizeClasses: Record<ButtonSize, string> = {
  xs: "h-7 px-2.5 text-[11px] gap-1 rounded",
  sm: "h-8 px-3 text-xs gap-1.5 rounded-badge",
  md: "h-9 px-4 text-sm gap-2 rounded-badge",
  lg: "h-11 px-6 text-base gap-2.5 rounded-badge",
};

const iconSize: Record<ButtonSize, number> = {
  xs: 11,
  sm: 13,
  md: 14,
  lg: 16,
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      loading = false,
      fullWidth = false,
      leftIcon,
      rightIcon,
      children,
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    const sz = iconSize[size];

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          "inline-flex items-center justify-center font-display font-medium",
          "transition-all duration-150 cursor-pointer select-none",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-1 focus-visible:ring-offset-bg",
          "disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none",
          variantClasses[variant],
          sizeClasses[size],
          fullWidth && "w-full",
          className
        )}
        {...props}
      >
        {loading ? (
          <Loader2 size={sz} className="animate-spin" />
        ) : leftIcon ? (
          <span className="flex items-center shrink-0">{leftIcon}</span>
        ) : null}
        <span>{children}</span>
        {!loading && rightIcon && (
          <span className="flex items-center shrink-0">{rightIcon}</span>
        )}
      </button>
    );
  }
);

Button.displayName = "Button";