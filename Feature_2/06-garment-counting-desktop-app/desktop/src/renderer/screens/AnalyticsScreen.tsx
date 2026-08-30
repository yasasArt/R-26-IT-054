import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  AnalyticsFilters,
  AnalyticsPayload,
  AnalyticsSession,
  DashboardPayload,
  Employee,
  ProductionSession,
} from "../../shared/types";
import { Icon } from "../components/Icon";
import { EmptyState, InlineNotice, MetricCard, ModeBadge, PageHeading } from "../components/OperatorUi";
import { SessionDetailsModal } from "../components/SessionDetailsModal";
import { analyticsQuery, api } from "../lib/api";
import { formatDateTime, formatDuration, formatNumber, humanizeMode } from "../lib/format";

type AnalyticsTab = "sessions" | "employees" | "pieces" | "iot";

interface Props {
  employees: Employee[];
  sessions: ProductionSession[];
}

const EMPTY_FILTERS: AnalyticsFilters = {
  employee_id: "",
  session_id: "",
  sewing_line: "",
  start_date: "",
  end_date: "",
  session_mode: "",
};

export function AnalyticsScreen({ employees, sessions }: Props) {
  const [filters, setFilters] = useState<AnalyticsFilters>(EMPTY_FILTERS);
  const [payload, setPayload] = useState<AnalyticsPayload | null>(null);
  const [activeTab, setActiveTab] = useState<AnalyticsTab>("sessions");
  const [loading, setLoading] = useState(true);
  const [exportingKey, setExportingKey] = useState<string | null>(null);
  const [selectedSession, setSelectedSession] = useState<AnalyticsSession | null>(null);
  const [sessionDetail, setSessionDetail] = useState<DashboardPayload | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sewingLines = useMemo(
    () => [...new Set(sessions.map((session) => session.sewing_line))].sort(),
    [sessions],
  );

  const refreshAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPayload(await api.analytics(filters));
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "The analytics report could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void refreshAnalytics();
  }, [refreshAnalytics]);

  const exportWorkbook = async (exportFilters: AnalyticsFilters, key: string, label: string) => {
    setExportingKey(key);
    setMessage(null);
    setError(null);
    try {
      const result = await window.garmentDesktop.exportAnalytics(analyticsQuery(exportFilters));
      if (!result.canceled) setMessage(`${label} Excel report was saved successfully.`);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "The Excel report could not be saved.");
    } finally {
      setExportingKey(null);
    }
  };

  const openSessionDetails = async (session: AnalyticsSession) => {
    setSelectedSession(session);
    setSessionDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    try {
      setSessionDetail(await api.dashboard(session.id));
    } catch (caughtError) {
      setDetailError(caughtError instanceof Error ? caughtError.message : "The session details could not be loaded.");
    } finally {
      setDetailLoading(false);
    }
  };

  const summary = payload?.summary;

  return (
    <div className="screen-stack">
      {selectedSession ? (
        <SessionDetailsModal
          session={selectedSession}
          detail={sessionDetail}
          loading={detailLoading}
          error={detailError}
          exporting={exportingKey === `session-${selectedSession.id}`}
          onClose={() => setSelectedSession(null)}
          onExport={() => void exportWorkbook(
            { ...EMPTY_FILTERS, session_id: String(selectedSession.id) },
            `session-${selectedSession.id}`,
            selectedSession.session_code,
          )}
        />
      ) : null}

      <PageHeading
        eyebrow="PRODUCTION INTELLIGENCE"
        title="Analytics"
        description="All past and active sessions remain available. Select a session to inspect its garment cycles and controller activity."
        action={
          <button type="button" className="action-button action-primary" disabled={exportingKey !== null || loading} onClick={() => void exportWorkbook(filters, "filtered", "Filtered production")}>
            <Icon name="download" size={16} /> {exportingKey === "filtered" ? "Preparing Excel…" : "Export filtered report"}
          </button>
        }
      />

      {error ? <InlineNotice tone="warning">{error}</InlineNotice> : null}
      {message ? <InlineNotice tone="success">{message}</InlineNotice> : null}

      <section className="panel analytics-filter-panel">
        <div className="filter-heading analytics-filter-heading">
          <div><h2>Filter production results</h2><p>Combine employee, session, line, date, and session-type filters.</p></div>
          <button type="button" className="action-button action-secondary" onClick={() => setFilters({ ...EMPTY_FILTERS })}>Clear filters</button>
        </div>
        <div className="analytics-filter-grid">
          <label><span>Employee</span><select className="form-select" value={filters.employee_id} onChange={(event) => setFilters((current) => ({ ...current, employee_id: event.target.value }))}><option value="">All employees</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.full_name}</option>)}</select></label>
          <label><span>Session</span><select className="form-select" value={filters.session_id} onChange={(event) => setFilters((current) => ({ ...current, session_id: event.target.value }))}><option value="">All sessions</option>{sessions.map((session) => <option key={session.id} value={session.id}>{session.session_code}</option>)}</select></label>
          <label><span>Sewing line</span><select className="form-select" value={filters.sewing_line} onChange={(event) => setFilters((current) => ({ ...current, sewing_line: event.target.value }))}><option value="">All sewing lines</option>{sewingLines.map((line) => <option key={line} value={line}>{line}</option>)}</select></label>
          <label><span>From date</span><input className="form-input" type="date" value={filters.start_date} onChange={(event) => setFilters((current) => ({ ...current, start_date: event.target.value }))} /></label>
          <label><span>To date</span><input className="form-input" type="date" value={filters.end_date} onChange={(event) => setFilters((current) => ({ ...current, end_date: event.target.value }))} /></label>
          <label><span>Session type</span><select className="form-select" value={filters.session_mode} onChange={(event) => setFilters((current) => ({ ...current, session_mode: event.target.value as AnalyticsFilters["session_mode"] }))}><option value="">All session types</option><option value="PRODUCTION">Production only</option><option value="VALIDATION">Validation only</option></select></label>
        </div>
      </section>

      <div className="metric-grid metric-grid-five">
        <MetricCard icon="folder" label="Sessions" value={formatNumber(summary?.session_count ?? 0)} detail={`${summary?.employee_count ?? 0} employees`} tone="blue" />
        <MetricCard icon="layers" label="Produced" value={formatNumber(summary?.total_pieces ?? 0)} detail={`${formatNumber(summary?.target_pieces ?? 0)} target pieces`} tone="green" />
        <MetricCard icon="target" label="Achievement" value={`${formatNumber(summary?.achievement_percent ?? 0, 1)}%`} detail="Weighted target attainment" tone="violet" />
        <MetricCard icon="refresh" label="Rework" value={formatNumber(summary?.rework_count ?? 0)} detail={formatDuration(summary?.rework_seconds ?? 0)} tone="amber" />
        <MetricCard icon="pause" label="Downtime" value={formatNumber(summary?.downtime_count ?? 0)} detail={formatDuration(summary?.downtime_seconds ?? 0)} tone="rose" />
      </div>

      <section className="panel analytics-results-panel">
        <div className="analytics-tabs" role="tablist" aria-label="Analytics data views">
          {([
            ["sessions", "Session register", payload?.sessions.length ?? 0],
            ["employees", "Employee performance", payload?.employees.length ?? 0],
            ["pieces", "Garment cycles", payload?.piece_events.length ?? 0],
            ["iot", "Controller events", payload?.iot_events.length ?? 0],
          ] as const).map(([tab, label, count]) => (
            <button key={tab} type="button" role="tab" aria-selected={activeTab === tab} className={`analytics-tab ${activeTab === tab ? "active" : ""}`} onClick={() => setActiveTab(tab)}>{label}<span>{count}</span></button>
          ))}
        </div>

        {loading ? <p className="table-empty-note">Updating filtered production results…</p> : !payload?.sessions.length ? (
          <EmptyState icon="report" title="No matching production records" description="Adjust the filters or complete a workstation session to see analytics here." />
        ) : (
          <div className="table-wrap">
            {activeTab === "sessions" ? (
              <table className="operator-table analytics-table">
                <thead><tr><th>Session</th><th>Employee</th><th>Sewing line</th><th>Type</th><th>Pieces</th><th>Achievement</th><th>Avg cycle</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>{payload.sessions.map((session) => (
                  <tr key={session.id} className="analytics-clickable-row" tabIndex={0} onClick={() => void openSessionDetails(session)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") void openSessionDetails(session); }}>
                    <td><strong>{session.session_code}</strong><span className="table-subline">{formatDateTime(session.started_at)}</span></td><td>{session.employee_name}</td><td>{session.sewing_line}</td><td><ModeBadge mode={session.session_mode} /></td><td>{session.total_pieces} / {session.target_pieces}</td><td>{formatNumber(session.achievement_percent, 1)}%</td><td>{session.average_cycle_seconds === null ? "—" : `${formatNumber(session.average_cycle_seconds, 1)} sec`}</td><td><ModeBadge mode={session.status} /></td>
                    <td><div className="table-action-row"><button type="button" className="table-action" onClick={(event) => { event.stopPropagation(); void openSessionDetails(session); }}>View</button><button type="button" className="table-action" disabled={exportingKey !== null} onClick={(event) => { event.stopPropagation(); void exportWorkbook({ ...EMPTY_FILTERS, session_id: String(session.id) }, `session-${session.id}`, session.session_code); }}>{exportingKey === `session-${session.id}` ? "Exporting…" : "Export"}</button></div></td>
                  </tr>
                ))}</tbody>
              </table>
            ) : null}
            {activeTab === "employees" ? (
              <table className="operator-table analytics-table">
                <thead><tr><th>Employee</th><th>Sewing line</th><th>Sessions</th><th>Produced</th><th>Target</th><th>Achievement</th><th>Rework</th><th>Downtime</th><th>Action</th></tr></thead>
                <tbody>{payload.employees.map((employee) => (
                  <tr key={employee.employee_id}><td><strong>{employee.employee_name}</strong><span className="table-subline">{employee.employee_code}</span></td><td>{employee.sewing_line}</td><td>{employee.session_count}</td><td>{employee.total_pieces}</td><td>{employee.target_pieces}</td><td>{formatNumber(employee.achievement_percent, 1)}%</td><td>{employee.rework_count} · {formatDuration(employee.rework_seconds)}</td><td>{employee.downtime_count} · {formatDuration(employee.downtime_seconds)}</td><td><button type="button" className="table-action" disabled={exportingKey !== null} onClick={() => void exportWorkbook({ ...EMPTY_FILTERS, employee_id: String(employee.employee_id) }, `employee-${employee.employee_id}`, employee.employee_name)}>{exportingKey === `employee-${employee.employee_id}` ? "Exporting…" : "Export employee"}</button></td></tr>
                ))}</tbody>
              </table>
            ) : null}
            {activeTab === "pieces" ? <table className="operator-table analytics-table"><thead><tr><th>Session ID</th><th>Piece</th><th>Cycle time</th><th>Completed</th><th>Transition</th><th>Source</th></tr></thead><tbody>{payload.piece_events.map((event) => <tr key={event.id}><td>#{event.session_id}</td><td><strong>Piece {event.piece_number}</strong></td><td>{formatNumber(event.cycle_seconds, 2)} sec</td><td>{formatDateTime(event.completed_at)}</td><td>SEWING → IDLE_SETUP</td><td><ModeBadge mode={event.event_source} /></td></tr>)}</tbody></table> : null}
            {activeTab === "iot" ? <table className="operator-table analytics-table"><thead><tr><th>Session ID</th><th>Controller action</th><th>Previous mode</th><th>New mode</th><th>Source</th><th>Recorded</th></tr></thead><tbody>{payload.iot_events.map((event) => <tr key={event.id}><td>#{event.session_id ?? "—"}</td><td><strong>{humanizeMode(event.event_type)}</strong></td><td><ModeBadge mode={event.mode_before} /></td><td><ModeBadge mode={event.mode_after} /></td><td><ModeBadge mode={event.event_source} /></td><td>{formatDateTime(event.occurred_at)}</td></tr>)}</tbody></table> : null}
          </div>
        )}
      </section>
    </div>
  );
}
