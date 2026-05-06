import type { ReactNode } from "react";

type Tone = "ok" | "warn" | "bad" | "info" | "cyan" | "orange" | "muted";

export function StatusPill({
  label,
  tone = "muted",
  pulse = false,
}: {
  label: string;
  tone?: Tone;
  pulse?: boolean;
}) {
  return (
    <span className={`status-pill ${tone === "muted" ? "" : tone}`}>
      <span className="dot" style={{ animation: pulse ? "fadeIn 1.1s ease-in-out infinite alternate" : undefined }} />
      {label}
    </span>
  );
}

export function Panel({
  title,
  eyebrow,
  action,
  children,
  className = "",
}: {
  title: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-header">
        <div>
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          <h2 className="panel-title">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function MetricCard({
  label,
  value,
  unit,
  sub,
  tone = "muted",
  badge,
}: {
  label: string;
  value: string | number;
  unit?: string;
  sub?: string;
  tone?: Tone;
  badge?: string;
}) {
  return (
    <article className="metric-card">
      <div className="metric-top">
        <div className="metric-label">{label}</div>
        {badge && <StatusPill label={badge} tone={tone} />}
      </div>
      <div>
        <div className={`metric-value ${tone === "muted" ? "" : tone}`}>
          <span>{value}</span>
          {unit && <span className="metric-unit">{unit}</span>}
        </div>
        {sub && <div className="metric-sub">{sub}</div>}
      </div>
    </article>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1 className="page-title">{title}</h1>
        {description && <p className="muted" style={{ maxWidth: 760, margin: "8px 0 0", lineHeight: 1.55 }}>{description}</p>}
      </div>
      {actions}
    </div>
  );
}

export function CameraFrame({
  mode,
  children,
}: {
  mode: "sewing" | "quality";
  children?: ReactNode;
}) {
  return (
    <div className="camera-frame">
      <div className="camera-overlay" />
      <div className="scan-line" />
      <div style={{ position: "absolute", top: 16, left: 16 }}>
        <StatusPill label={mode === "sewing" ? "Output zone live" : "Inspection camera live"} tone="ok" pulse />
      </div>
      {children}
    </div>
  );
}

export function MiniBarChart({
  values,
  tone = "info",
}: {
  values: number[];
  tone?: Tone;
}) {
  const max = Math.max(...values, 1);
  return (
    <div className="bar-chart" aria-label="bar chart">
      {values.map((value, index) => (
        <div
          key={`${value}-${index}`}
          className={`bar ${tone === "muted" ? "" : tone}`}
          style={{ height: `${Math.max((value / max) * 100, 8)}%` }}
          title={`${value}`}
        />
      ))}
    </div>
  );
}

export function DataTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: Array<Array<ReactNode>>;
}) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>{headers.map(header => <th key={header}>{header}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
