import type { ReadinessState } from "../../shared/types";
import { Icon } from "./Icon";

const badgeLabels: Record<ReadinessState, string> = {
  ready: "Ready",
  attention: "Checkpoint found",
  pending: "Upcoming phase",
  blocked: "Action needed",
};

export function StatusBadge({ status }: { status: ReadinessState }) {
  return (
    <span className={`status-badge status-${status}`}>
      {status === "ready" ? <Icon name="check" size={13} /> : <span className="status-dot" />}
      {badgeLabels[status]}
    </span>
  );
}
