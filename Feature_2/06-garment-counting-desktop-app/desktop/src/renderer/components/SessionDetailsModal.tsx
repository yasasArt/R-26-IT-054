import type { AnalyticsSession, DashboardPayload } from "../../shared/types";
import { formatDateTime, formatDuration, formatNumber, humanizeMode } from "../lib/format";
import { Icon } from "./Icon";
import { EmptyState, InlineNotice, MetricCard, ModeBadge } from "./OperatorUi";

interface Props {
  session: AnalyticsSession;
  detail: DashboardPayload | null;
  loading: boolean;
  error: string | null;
  exporting: boolean;
  onClose: () => void;
  onExport: () => void;
}

export function SessionDetailsModal({ session, detail, loading, error, exporting, onClose, onExport }: Props) {
  return (
    <div className="analytics-detail-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="analytics-detail-modal" role="dialog" aria-modal="true" aria-labelledby="session-detail-title">
        <header className="analytics-detail-heading">
          <div>
            <span className="eyebrow">SESSION DETAILS</span>
            <h2 id="session-detail-title">{session.session_code}</h2>
            <p>{session.employee_name} · {session.sewing_line} · {formatDateTime(session.started_at)}</p>
          </div>
          <div className="analytics-detail-actions">
            <button type="button" className="action-button action-primary" disabled={exporting} onClick={onExport}>
              <Icon name="download" size={15} /> {exporting ? "Preparing…" : "Export this session"}
            </button>
            <button type="button" className="icon-action" aria-label="Close session details" onClick={onClose}>
              <Icon name="close" size={17} />
            </button>
          </div>
        </header>

        <div className="analytics-detail-meta">
          <span><strong>Employee</strong>{session.employee_code} · {session.employee_name}</span>
          <span><strong>Workstation</strong>{session.workstation_id}</span>
          <span><strong>Camera</strong>{session.camera_label}</span>
          <span><strong>Session type</strong><ModeBadge mode={session.session_mode} /></span>
          <span><strong>Status</strong><ModeBadge mode={session.status} /></span>
          <span><strong>Ended</strong>{session.ended_at ? formatDateTime(session.ended_at) : "Session is active"}</span>
        </div>

        {error ? <InlineNotice tone="warning">{error}</InlineNotice> : null}
        {loading ? <p className="table-empty-note">Loading garment cycles and controller activity…</p> : detail ? (
          <>
            <div className="metric-grid analytics-detail-metrics">
              <MetricCard icon="layers" label="Produced" value={`${detail.session.total_pieces} / ${detail.session.target_pieces}`} detail={`${formatNumber(detail.session.achievement_percent, 1)}% achievement`} tone="green" />
              <MetricCard icon="target" label="Average cycle" value={detail.session.average_cycle_seconds === null ? "—" : `${formatNumber(detail.session.average_cycle_seconds, 1)} sec`} detail={`${detail.piece_events.length} measured cycles`} tone="blue" />
              <MetricCard icon="refresh" label="Rework" value={formatNumber(detail.iot_metrics.rework_count)} detail={formatDuration(detail.iot_metrics.rework_seconds)} tone="amber" />
              <MetricCard icon="pause" label="Downtime" value={formatNumber(detail.iot_metrics.downtime_count)} detail={formatDuration(detail.iot_metrics.downtime_seconds)} tone="rose" />
            </div>

            <div className="analytics-detail-section">
              <div className="analytics-detail-section-heading"><h3>Garment cycle detail</h3><span>{detail.piece_events.length} pieces</span></div>
              {detail.piece_events.length ? (
                <div className="table-wrap analytics-detail-table-wrap">
                  <table className="operator-table analytics-table">
                    <thead><tr><th>Piece</th><th>Cycle time</th><th>Sewing started</th><th>Completed</th><th>Source</th></tr></thead>
                    <tbody>{detail.piece_events.map((event) => (
                      <tr key={event.id}><td><strong>Piece {event.piece_number}</strong></td><td>{formatNumber(event.cycle_seconds, 2)} sec</td><td>{event.sewing_started_at ? formatDateTime(event.sewing_started_at) : "—"}</td><td>{formatDateTime(event.completed_at)}</td><td><ModeBadge mode={event.event_source} /></td></tr>
                    ))}</tbody>
                  </table>
                </div>
              ) : <EmptyState icon="layers" title="No completed garments" description="This session does not contain a confirmed garment cycle yet." />}
            </div>

            <div className="analytics-detail-section">
              <div className="analytics-detail-section-heading"><h3>Controller activity</h3><span>{detail.iot_events.length} events</span></div>
              {detail.iot_events.length ? (
                <div className="table-wrap analytics-detail-table-wrap">
                  <table className="operator-table analytics-table">
                    <thead><tr><th>Action</th><th>Previous mode</th><th>New mode</th><th>Source</th><th>Recorded</th></tr></thead>
                    <tbody>{detail.iot_events.map((event) => (
                      <tr key={event.id}><td><strong>{humanizeMode(event.event_type)}</strong></td><td><ModeBadge mode={event.mode_before} /></td><td><ModeBadge mode={event.mode_after} /></td><td><ModeBadge mode={event.event_source} /></td><td>{formatDateTime(event.occurred_at)}</td></tr>
                    ))}</tbody>
                  </table>
                </div>
              ) : <EmptyState icon="bluetooth" title="No controller events" description="No rework, downtime, reset, or connection event was recorded for this session." />}
            </div>
          </>
        ) : null}
      </section>
    </div>
  );
}
