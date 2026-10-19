export function formatNumber(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";

  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";

  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return "—";

  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "—";
  if (seconds < 60) return `${formatNumber(seconds, 1)} sec`;

  const minutes = Math.floor(seconds / 60);
  const remainder = Math.floor(seconds % 60);
  return `${minutes}m ${remainder}s`;
}

export function humanizeMode(value: string): string {
  if (value === "NORMAL") return "Normal production";
  if (value === "REWORK") return "Rework in progress";
  if (value === "DOWNTIME") return "Downtime in progress";
  if (value === "DISCONNECTED") return "Controller disconnected";
  if (value === "RECONNECTED") return "Controller reconnected";
  if (value === "RESET") return "Returned to normal";
  return value;
}
