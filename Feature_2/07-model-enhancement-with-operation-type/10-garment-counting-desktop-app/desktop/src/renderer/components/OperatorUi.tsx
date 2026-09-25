import type { ReactNode } from "react";

import type { CycleTimeStatus, OperationType } from "../../shared/types";
import { Icon, type IconName } from "./Icon";

export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action ? <div className="page-heading-action">{action}</div> : null}
    </div>
  );
}

export function MetricCard({
  icon,
  label,
  value,
  detail,
  tone = "blue",
}: {
  icon: IconName;
  label: string;
  value: string | number;
  detail: string;
  tone?: "blue" | "green" | "amber" | "rose" | "violet";
}) {
  return (
    <article className={`metric-card metric-${tone}`}>
      <div className="metric-topline">
        <span>{label}</span>
        <span className="metric-icon">
          <Icon name={icon} size={17} />
        </span>
      </div>
      <strong className="metric-value">{value}</strong>
      <span className="metric-detail">{detail}</span>
    </article>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: IconName;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="operator-empty-state">
      <span className="empty-state-icon">
        <Icon name={icon} size={24} />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function InlineNotice({
  tone = "info",
  children,
}: {
  tone?: "info" | "warning" | "success";
  children: ReactNode;
}) {
  return (
    <div className={`inline-notice notice-${tone}`}>
      <Icon name={tone === "success" ? "check" : tone === "warning" ? "warning" : "shield"} size={17} />
      <span>{children}</span>
    </div>
  );
}

export function ModeBadge({ mode }: { mode: string }) {
  const normalized = mode.toLowerCase();
  return <span className={`mode-badge mode-${normalized}`}>{mode.replaceAll("_", " ")}</span>;
}

export function operationLabel(operation: OperationType | null): string {
  if (!operation) return "Not recorded";
  return operation.charAt(0) + operation.slice(1).toLowerCase();
}

export function CycleStatusBadge({ status }: { status: CycleTimeStatus }) {
  const label = status === "WITHIN_ESTIMATE"
    ? "Within estimate"
    : status === "OVER_ESTIMATE"
      ? "Over estimate"
      : "No estimate";

  return <span className={`cycle-status-badge cycle-status-${status.toLowerCase()}`}>{label}</span>;
}
