import { clsx, type ClassValue } from "clsx";
import { format, formatDistanceToNow, differenceInSeconds } from "date-fns";
import type { OperatorStatus, CameraStatus, IoTStatus, QualityDecision, Severity } from "@/lib/types";

// ─────────────────────────────────────────
// CLASSNAME UTILITY
// ─────────────────────────────────────────

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

// ─────────────────────────────────────────
// TIME / DATE FORMATTING
// ─────────────────────────────────────────

export function formatTime(date: Date): string {
  return format(date, "HH:mm:ss");
}

export function formatDateTime(date: Date): string {
  return format(date, "dd/MM/yyyy HH:mm:ss");
}

export function formatShortDate(date: Date): string {
  return format(date, "dd MMM yyyy");
}

export function formatRelative(date: Date): string {
  return formatDistanceToNow(date, { addSuffix: true });
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return `${h}h ${rem}m`;
}

export function getElapsedSeconds(from: Date): number {
  return differenceInSeconds(new Date(), from);
}

// ─────────────────────────────────────────
// ID GENERATION
// ─────────────────────────────────────────

export function generateId(prefix = "evt"): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

// ─────────────────────────────────────────
// STATUS → COLOUR MAPPINGS
// ─────────────────────────────────────────

export function getOperatorStatusColor(status: OperatorStatus): string {
  const map: Record<OperatorStatus, string> = {
    active:   "text-success",
    idle:     "text-text-muted",
    downtime: "text-danger",
    rework:   "text-warning",
  };
  return map[status];
}

export function getOperatorStatusBg(status: OperatorStatus): string {
  const map: Record<OperatorStatus, string> = {
    active:   "bg-success/10 text-success border-success/30",
    idle:     "bg-dim/20 text-text-muted border-dim/30",
    downtime: "bg-danger/10 text-danger border-danger/30",
    rework:   "bg-warning/10 text-warning border-warning/30",
  };
  return map[status];
}

export function getCameraStatusColor(status: CameraStatus): string {
  const map: Record<CameraStatus, string> = {
    live:         "text-success",
    disconnected: "text-danger",
    error:        "text-danger",
    calibrating:  "text-warning",
  };
  return map[status];
}

export function getIoTStatusColor(status: IoTStatus): string {
  const map: Record<IoTStatus, string> = {
    connected:    "text-success",
    disconnected: "text-danger",
    error:        "text-danger",
  };
  return map[status];
}

export function getDecisionStyle(decision: QualityDecision): {
  bg: string;
  text: string;
  border: string;
  glow: string;
} {
  const map: Record<QualityDecision, { bg: string; text: string; border: string; glow: string }> = {
    PASS:     { bg: "bg-success/10", text: "text-success", border: "border-success/40", glow: "shadow-glow-green" },
    REWORK:   { bg: "bg-warning/10", text: "text-warning", border: "border-warning/40", glow: "shadow-glow-yellow" },
    MISMATCH: { bg: "bg-danger/10",  text: "text-danger",  border: "border-danger/40",  glow: "shadow-glow-red" },
  };
  return map[decision];
}

export function getSeverityStyle(severity: Severity): string {
  const map: Record<Severity, string> = {
    info:    "text-accent",
    warning: "text-warning",
    error:   "text-danger",
    success: "text-success",
  };
  return map[severity];
}

// ─────────────────────────────────────────
// CYCLE TIME STATUS
// ─────────────────────────────────────────

export function getCycleTimeStatus(
  seconds: number,
  target = 45,
  warning = 65,
  danger = 90
): "success" | "warning" | "danger" {
  if (seconds <= target) return "success";
  if (seconds <= warning) return "warning";
  return "danger";
}

export function getCycleTimeColor(
  seconds: number,
  target = 45,
  warning = 65,
  danger = 90
): string {
  const status = getCycleTimeStatus(seconds, target, warning, danger);
  return {
    success: "text-success",
    warning: "text-warning",
    danger:  "text-danger",
  }[status];
}

// ─────────────────────────────────────────
// NUMBER FORMATTING
// ─────────────────────────────────────────

export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`;
}

export function formatCm(value: number): string {
  return `${value.toFixed(1)} cm`;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function randomBetween(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

export function randomFloat(min: number, max: number, decimals = 1): number {
  return parseFloat((Math.random() * (max - min) + min).toFixed(decimals));
}