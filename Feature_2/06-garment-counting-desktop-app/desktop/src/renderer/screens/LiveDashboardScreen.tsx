import { useCallback, useEffect, useState } from "react";

import { getProgressPercent } from "../../shared/chart-data";
import type { DashboardPayload, IotEventType, ProductionSession } from "../../shared/types";
import { CycleTimeChart, TargetCountdownChart } from "../components/ProductionCharts";
import { Icon } from "../components/Icon";
import { EmptyState, InlineNotice, MetricCard, ModeBadge, PageHeading } from "../components/OperatorUi";
import { VisionMonitor } from "../components/VisionMonitor";
import { api } from "../lib/api";
import { useBluetoothController } from "../lib/bluetooth-controller";
import { formatDuration, formatNumber, formatTime, humanizeMode } from "../lib/format";

interface Props {
  session: ProductionSession | null;
  onSessionUpdated: (session: ProductionSession) => void;
  onSessionCompleted: (session: ProductionSession) => void;
  onCreateSession: () => void;
}

export function LiveDashboardScreen({ session, onSessionUpdated, onSessionCompleted, onCreateSession }: Props) {
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const controller = useBluetoothController();
  const sessionId = session?.id ?? null;

  const loadDashboard = useCallback(async () => {
    if (!sessionId) return;

    try {
      const nextDashboard = await api.dashboard(sessionId);
      setDashboard(nextDashboard);
      onSessionUpdated(nextDashboard.session);
      setError(null);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Live production details could not be refreshed.");
    }
  }, [onSessionUpdated, sessionId]);

  useEffect(() => {
    void loadDashboard();

    if (!sessionId) return;

    const timer = window.setInterval(() => void loadDashboard(), 1200);
    return () => window.clearInterval(timer);
  }, [loadDashboard, sessionId]);

  useEffect(() => {
    if (!sessionId || (!controller.deviceId && !controller.lastButtonAt)) return;
    void loadDashboard();
  }, [controller.deviceId, controller.lastButtonAt, controller.phase, loadDashboard, sessionId]);

  if (!session) {
    return (
      <div className="screen-stack">
        <PageHeading eyebrow="LIVE PRODUCTION" title="No active session" description="Create a session after configuring the workstation devices." />
        <EmptyState
          icon="play"
          title="Production has not started"
          description="Select an employee and a production target before opening the live workstation dashboard."
          action={<button type="button" className="action-button action-primary" onClick={onCreateSession}>Create a session</button>}
        />
      </div>
    );
  }

  const current = dashboard?.session ?? session;
  const progress = getProgressPercent(current.total_pieces, current.target_pieces);
  const metrics = dashboard?.iot_metrics;
  const disconnected = dashboard?.device_configuration.iot_connected === false;

  const runAction = async (name: string, action: () => Promise<unknown>) => {
    setBusyAction(name);
    setError(null);

    try {
      await action();
      await loadDashboard();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "The workstation action could not be completed.");
    } finally {
      setBusyAction(null);
    }
  };

  const sendIotEvent = (eventType: IotEventType) =>
    runAction(eventType, () => api.createValidationIotEvent(current.id, eventType));

  const finishSession = async () => {
    setBusyAction("complete");
    setError(null);

    try {
      const completed = await api.completeSession(current.id);
      onSessionCompleted(completed);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "The current session could not be ended.");
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <div className="screen-stack">
      <PageHeading
        eyebrow="STEP 03 · LIVE WORKSTATION"
        title="Live production dashboard"
        description={`${current.employee_name} · ${current.sewing_line} · ${current.workstation_id}`}
        action={
          <button type="button" className="action-button action-secondary" disabled={busyAction !== null} onClick={() => void finishSession()}>
            <Icon name="pause" size={16} /> End session
          </button>
        }
      />

      {error ? <InlineNotice tone="warning">{error}</InlineNotice> : null}
      {current.session_mode === "VALIDATION" ? (
        <InlineNotice tone="warning">Validation session: real AI camera or recorded-video recognition is available, but all garment counts and simulated controller presses remain clearly labeled as validation.</InlineNotice>
      ) : null}
      {disconnected ? (
        <InlineNotice tone="warning">
          {controller.phase === "RECONNECTING"
            ? `Controller connection lost. Reconnecting automatically (attempt ${controller.reconnectAttempt || 1}). Press Button A to wake the device. Garment counting is safely paused.`
            : "The operator controller is disconnected. The current garment count is preserved, but new pieces cannot be recorded."}
        </InlineNotice>
      ) : null}

      <section className="production-hero">
        <div className="production-hero-copy">
          <span className="eyebrow eyebrow-inverse">CURRENT WORKSTATION STATUS</span>
          <h2>{humanizeMode(disconnected ? "DISCONNECTED" : current.operator_mode)}</h2>
          <p>{current.session_code} · Started {formatTime(current.started_at)}</p>
          <div className="production-progress-track"><span style={{ width: `${progress}%` }} /></div>
          <span className="production-progress-label">{progress}% of the session target completed</span>
        </div>
        <div className="production-counter">
          <span>Completed pieces</span>
          <strong>{formatNumber(current.total_pieces)}</strong>
          <span>of {formatNumber(current.target_pieces)} target</span>
        </div>
      </section>

      <div className="metric-grid metric-grid-five">
        <MetricCard icon="layers" label="Produced" value={formatNumber(current.total_pieces)} detail="Confirmed garment pieces" tone="blue" />
        <MetricCard icon="target" label="Remaining" value={formatNumber(current.remaining_pieces)} detail="Pieces to hit target" tone="green" />
        <MetricCard icon="clock" label="Avg cycle" value={current.average_cycle_seconds === null ? "—" : `${formatNumber(current.average_cycle_seconds, 1)}s`} detail="Includes the first piece" tone="violet" />
        <MetricCard icon="refresh" label="Rework" value={formatNumber(metrics?.rework_count ?? 0)} detail={formatDuration(metrics?.rework_seconds ?? 0)} tone="amber" />
        <MetricCard icon="pause" label="Downtime" value={formatNumber(metrics?.downtime_count ?? 0)} detail={formatDuration(metrics?.downtime_seconds ?? 0)} tone="rose" />
      </div>

      <VisionMonitor session={current} inference={dashboard?.inference ?? null} refresh={loadDashboard} />

      {current.session_mode === "PRODUCTION" ? (
        <section className="panel physical-controller-panel">
          <div className="physical-controller-heading">
            <span className="device-feature-icon icon-controller"><Icon name="bluetooth" size={20} /></span>
            <div><span className="eyebrow">LIVE OPERATOR CONTROLLER</span><h2>{dashboard?.device_configuration.iot_device_name ?? "GarmentCounter-IoT"}</h2></div>
            <span className={`connection-pill ${disconnected ? "is-pending" : "is-connected"}`}>{disconnected ? "Reconnecting" : "Live"}</span>
          </div>
          <div className="physical-controller-actions">
            <span><strong>B</strong>Rework</span><span><strong>C</strong>Downtime</span><span><strong>D</strong>Return to normal</span>
          </div>
          <p>{controller.lastButton ? `Latest physical button: ${controller.lastButton} · recorded instantly in the session history.` : "Press a controller button to record operator activity in this production session."}</p>
        </section>
      ) : null}

      <div className="chart-split-grid">
        <section className="panel chart-panel">
          <header className="chart-panel-heading"><div><span className="eyebrow">PER-GARMENT PERFORMANCE</span><h2>Cycle time by piece</h2></div><span>seconds</span></header>
          <CycleTimeChart events={dashboard?.piece_events ?? []} />
        </section>
        <section className="panel chart-panel">
          <header className="chart-panel-heading"><div><span className="eyebrow">TARGET PROGRESS</span><h2>Pieces remaining</h2></div><span>step-down</span></header>
          <TargetCountdownChart points={dashboard?.target_series ?? [{ piece_number: 0, remaining_pieces: current.target_pieces }]} target={current.target_pieces} />
        </section>
      </div>

      {current.session_mode === "VALIDATION" ? (
        <section className="panel validation-controls">
          <div className="section-intro"><h2>Controller and database validation</h2><p>Test operator button behavior, safe counting pauses, database persistence, and analytics without creating production output.</p></div>
          <div className="button-row validation-button-row">
            <button type="button" className="action-button action-primary" disabled={busyAction !== null || current.operator_mode !== "NORMAL" || disconnected} onClick={() => void runAction("piece", () => api.addValidationPiece(current.id))}><Icon name="plus" size={16} /> Add validation piece</button>
            <button type="button" className="action-button action-secondary" disabled={busyAction !== null || disconnected} onClick={() => void sendIotEvent("REWORK")}>Rework press</button>
            <button type="button" className="action-button action-secondary" disabled={busyAction !== null || disconnected} onClick={() => void sendIotEvent("DOWNTIME")}>Downtime press</button>
            <button type="button" className="action-button action-secondary" disabled={busyAction !== null || disconnected} onClick={() => void sendIotEvent("RESET")}>Reset / normal</button>
            <button type="button" className="action-button action-secondary" disabled={busyAction !== null} onClick={() => void sendIotEvent(disconnected ? "RECONNECTED" : "DISCONNECTED")}>{disconnected ? "Reconnect test" : "Disconnect test"}</button>
          </div>
        </section>
      ) : null}

      <div className="activity-split-grid">
        <section className="panel event-panel">
          <header className="chart-panel-heading"><div><span className="eyebrow">LATEST COMPLETIONS</span><h2>Garment piece events</h2></div></header>
          {(dashboard?.piece_events.length ?? 0) ? (
            <div className="table-wrap"><table className="operator-table"><thead><tr><th>Piece</th><th>Cycle time</th><th>Recorded</th></tr></thead><tbody>
              {[...(dashboard?.piece_events ?? [])].reverse().slice(0, 8).map((event) => (
                <tr key={event.id}><td>#{event.piece_number}</td><td>{formatNumber(event.cycle_seconds, 1)} sec</td><td>{formatTime(event.completed_at)}</td></tr>
              ))}
            </tbody></table></div>
          ) : <p className="table-empty-note">No garments have been completed yet.</p>}
        </section>
        <section className="panel event-panel">
          <header className="chart-panel-heading"><div><span className="eyebrow">CONTROLLER ACTIVITY</span><h2>Operator button events</h2></div></header>
          {(dashboard?.iot_events.length ?? 0) ? (
            <div className="table-wrap"><table className="operator-table"><thead><tr><th>Action</th><th>Mode</th><th>Time</th></tr></thead><tbody>
              {(dashboard?.iot_events ?? []).slice(0, 8).map((event) => (
                <tr key={event.id}><td>{humanizeMode(event.event_type)}</td><td><ModeBadge mode={event.mode_after} /></td><td>{formatTime(event.occurred_at)}</td></tr>
              ))}
            </tbody></table></div>
          ) : <p className="table-empty-note">Controller button presses will appear here.</p>}
        </section>
      </div>
    </div>
  );
}
