import { useMemo, useState, type FormEvent } from "react";

import type { DeviceConfiguration, Employee, OperationType, ProductionSession, SessionMode, SystemReadiness } from "../../shared/types";
import { api } from "../lib/api";
import { Icon } from "../components/Icon";
import { EmptyState, InlineNotice, operationLabel, PageHeading } from "../components/OperatorUi";

interface Props {
  employees: Employee[];
  configuration: DeviceConfiguration | null;
  readiness: SystemReadiness | null;
  activeSession: ProductionSession | null;
  onSessionCreated: (session: ProductionSession) => void;
  onManageEmployees: () => void;
  onOpenSetup: () => void;
}

export function NewSessionScreen({
  employees,
  configuration,
  readiness,
  activeSession,
  onSessionCreated,
  onManageEmployees,
  onOpenSetup,
}: Props) {
  const [employeeId, setEmployeeId] = useState("");
  const [targetPieces, setTargetPieces] = useState("");
  const [operationType, setOperationType] = useState<OperationType>("COLLAR");
  const [estimatedCycleTime, setEstimatedCycleTime] = useState("");
  const [workstationId, setWorkstationId] = useState("WS-01");
  const [mode, setMode] = useState<SessionMode>(readiness?.productionReady ? "PRODUCTION" : "VALIDATION");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedEmployee = useMemo(
    () => employees.find((employee) => employee.id === Number(employeeId)) ?? null,
    [employees, employeeId],
  );

  const startSession = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const session = await api.createSession({
        employee_id: Number(employeeId),
        target_pieces: Number(targetPieces),
        operation_type: operationType,
        estimated_cycle_time_sec: Number(estimatedCycleTime),
        workstation_id: workstationId.trim(),
        session_mode: mode,
      });
      onSessionCreated(session);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "The session could not be started.");
    } finally {
      setSubmitting(false);
    }
  };

  if (activeSession) {
    return (
      <div className="screen-stack">
        <PageHeading eyebrow="STEP 02 · SESSION SETUP" title="A session is already active" description="Continue the current workstation session before starting another one." />
        <EmptyState
          icon="activity"
          title={activeSession.employee_name}
          description={`${activeSession.session_code} · ${activeSession.sewing_line} · ${activeSession.total_pieces} pieces completed`}
          action={<button type="button" className="action-button action-primary" onClick={() => onSessionCreated(activeSession)}>Open live production</button>}
        />
      </div>
    );
  }

  if (!employees.length) {
    return (
      <div className="screen-stack">
        <PageHeading eyebrow="STEP 02 · SESSION SETUP" title="Create a production session" description="Choose an employee, confirm the assigned sewing line, and enter today's target." />
        <EmptyState
          icon="users"
          title="Add your first employee"
          description="Employee names and assigned sewing lines are managed in Settings. Once added, operators can be selected from the session dropdown."
          action={<button type="button" className="action-button action-primary" onClick={onManageEmployees}><Icon name="plus" size={16} /> Add employees</button>}
        />
      </div>
    );
  }

  return (
    <div className="screen-stack">
      <PageHeading
        eyebrow="STEP 02 · SESSION SETUP"
        title="Create a production session"
        description="Choose the operator, garment operation, expected cycle time, and production target."
      />

      {error ? <InlineNotice tone="warning">{error}</InlineNotice> : null}
      {!configuration?.camera_tested ? (
        <InlineNotice tone="warning">The sewing camera has not been tested. Return to device setup before continuing.</InlineNotice>
      ) : null}

      <form className="session-layout" onSubmit={(event) => void startSession(event)}>
        <section className="panel session-form-card">
          <div className="section-intro">
            <h2>Operator and operation target</h2>
            <p>The selected operation provides context for cycle-time monitoring. It is not passed into the state classifier.</p>
          </div>

          <label className="field-label" htmlFor="session-employee">Employee</label>
          <select id="session-employee" className="form-select" value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} required>
            <option value="">Select an employee</option>
            {employees.map((employee) => (
              <option key={employee.id} value={employee.id}>{employee.full_name} · {employee.employee_code}</option>
            ))}
          </select>

          <label className="field-label" htmlFor="session-line">Assigned sewing line</label>
          <input id="session-line" className="form-input readonly-input" value={selectedEmployee?.sewing_line ?? "Select an employee to show the sewing line"} readOnly />

          <div className="two-field-grid">
            <div>
              <label className="field-label" htmlFor="operation-type">Garment operation</label>
              <select
                id="operation-type"
                className="form-select"
                value={operationType}
                onChange={(event) => setOperationType(event.target.value as OperationType)}
                required
              >
                <option value="COLLAR">Collar sewing</option>
                <option value="POCKET">Pocket sewing</option>
                <option value="SLEEVE">Sleeve sewing</option>
              </select>
            </div>
            <div>
              <label className="field-label" htmlFor="estimated-cycle-time">Estimated cycle time</label>
              <div className="input-with-unit">
                <input
                  id="estimated-cycle-time"
                  className="form-input"
                  type="number"
                  min={0.1}
                  max={3600}
                  step={0.1}
                  placeholder="e.g. 24.5"
                  value={estimatedCycleTime}
                  onChange={(event) => setEstimatedCycleTime(event.target.value)}
                  required
                />
                <span>seconds</span>
              </div>
            </div>
          </div>

          <div className="two-field-grid">
            <div>
              <label className="field-label" htmlFor="target-pieces">Target pieces</label>
              <input
                id="target-pieces"
                className="form-input"
                type="number"
                min={1}
                max={100000}
                placeholder="e.g. 120"
                value={targetPieces}
                onChange={(event) => setTargetPieces(event.target.value)}
                required
              />
            </div>
            <div>
              <label className="field-label" htmlFor="workstation-id">Workstation ID</label>
              <input id="workstation-id" className="form-input" value={workstationId} onChange={(event) => setWorkstationId(event.target.value)} required />
            </div>
          </div>

          <label className="field-label" htmlFor="session-camera">Configured camera</label>
          <input id="session-camera" className="form-input readonly-input" value={configuration?.camera_label || "No camera configured"} readOnly />

          <label className="field-label" htmlFor="session-mode">Session type</label>
          <select id="session-mode" className="form-select" value={mode} onChange={(event) => setMode(event.target.value as SessionMode)}>
            <option value="PRODUCTION" disabled={!readiness?.productionReady}>Production · requires all physical devices and models</option>
            <option value="VALIDATION" disabled={!readiness?.validationReady}>Validation · explicitly labeled test session</option>
          </select>

          {mode === "VALIDATION" ? (
            <InlineNotice tone="warning">This is a validation session. Simulated pieces and controller events are clearly labeled and are never reported as production data.</InlineNotice>
          ) : null}

          <div className="button-row session-form-actions">
            <button type="button" className="action-button action-secondary" onClick={onOpenSetup}>Back to device setup</button>
            <button
              type="submit"
              className="action-button action-primary action-large"
              disabled={submitting || !employeeId || !targetPieces || !estimatedCycleTime || Number(estimatedCycleTime) <= 0 || !configuration?.camera_tested || (mode === "VALIDATION" ? !readiness?.validationReady : !readiness?.productionReady)}
            >
              <Icon name="play" size={16} /> {submitting ? "Starting…" : "Start session"}
            </button>
          </div>
        </section>

        <aside className="panel session-summary-card">
          <span className="eyebrow">SESSION PREVIEW</span>
          <h2>{selectedEmployee?.full_name || "Select an employee"}</h2>
          <div className="summary-pair"><span>Sewing line</span><strong>{selectedEmployee?.sewing_line || "—"}</strong></div>
          <div className="summary-pair"><span>Operation</span><strong>{operationLabel(operationType)}</strong></div>
          <div className="summary-pair"><span>Estimated cycle</span><strong>{estimatedCycleTime ? `${estimatedCycleTime} sec` : "—"}</strong></div>
          <div className="summary-pair"><span>Workstation</span><strong>{workstationId || "—"}</strong></div>
          <div className="summary-pair"><span>Camera</span><strong>{configuration?.camera_label || "Not configured"}</strong></div>
          <div className="summary-pair"><span>Controller</span><strong>{configuration?.iot_mode === "SIMULATED" ? "Validation controller" : configuration?.iot_device_name || "Not configured"}</strong></div>
          <div className="target-preview"><span>Today's target</span><strong>{targetPieces || "—"}</strong><span>garment pieces</span></div>
        </aside>
      </form>
    </div>
  );
}
