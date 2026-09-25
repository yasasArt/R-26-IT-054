import { useState, type FormEvent } from "react";

import type { DeviceConfiguration, Employee, EmployeeInput, ProductionSession, SystemReadiness } from "../../shared/types";
import { Icon } from "../components/Icon";
import { EmptyState, InlineNotice, ModeBadge, PageHeading } from "../components/OperatorUi";
import { api } from "../lib/api";
import { DeviceSetupScreen } from "./DeviceSetupScreen";

interface Props {
  employees: Employee[];
  sessions: ProductionSession[];
  configuration: DeviceConfiguration | null;
  readiness: SystemReadiness | null;
  activeSession: ProductionSession | null;
  onUpdated: () => Promise<void>;
}

const emptyEmployee: EmployeeInput = { employee_code: "", full_name: "", sewing_line: "" };
const deleteConfirmationPhrase = "DELETE SESSION DATA";

export function SettingsScreen({ employees, sessions, configuration, readiness, activeSession, onUpdated }: Props) {
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [draft, setDraft] = useState<EmployeeInput>(emptyEmployee);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deletingHistory, setDeletingHistory] = useState(false);

  const editEmployee = (employee: Employee) => {
    setEditingEmployee(employee);
    setDraft({
      employee_code: employee.employee_code,
      full_name: employee.full_name,
      sewing_line: employee.sewing_line,
      active: employee.active,
    });
  };

  const saveEmployee = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      if (editingEmployee) {
        await api.updateEmployee(editingEmployee.id, { ...draft, active: draft.active ?? true });
      } else {
        await api.createEmployee({
          employee_code: draft.employee_code,
          full_name: draft.full_name,
          sewing_line: draft.sewing_line,
        });
      }

      await onUpdated();
      setMessage(editingEmployee ? "Employee information updated successfully." : "New employee added successfully.");
      setEditingEmployee(null);
      setDraft(emptyEmployee);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "The employee record could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const closeDeleteDialog = () => {
    if (deletingHistory) return;
    setDeleteDialogOpen(false);
    setDeleteConfirmation("");
  };

  const deleteSessionHistory = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (deleteConfirmation !== deleteConfirmationPhrase || activeSession || deletingHistory) return;

    setDeletingHistory(true);
    setError(null);
    setMessage(null);

    try {
      const result = await api.deleteSessionHistory(deleteConfirmation);
      await onUpdated();
      setDeleteDialogOpen(false);
      setDeleteConfirmation("");
      setMessage(
        `Deleted ${result.deleted_sessions} session${result.deleted_sessions === 1 ? "" : "s"}, ` +
        `${result.deleted_piece_events} garment cycle${result.deleted_piece_events === 1 ? "" : "s"}, and ` +
        `${result.deleted_iot_events} session controller event${result.deleted_iot_events === 1 ? "" : "s"}. ` +
        "Employee records and device settings were preserved.",
      );
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Stored session data could not be deleted.");
    } finally {
      setDeletingHistory(false);
    }
  };

  return (
    <div className="screen-stack">
      <PageHeading
        eyebrow="WORKSTATION SETTINGS"
        title="Employees and devices"
        description="Manage sewing operators, assigned lines, workstation devices, and stored production history."
      />

      {error ? <InlineNotice tone="warning">{error}</InlineNotice> : null}
      {message ? <InlineNotice tone="success">{message}</InlineNotice> : null}

      <div className="settings-employee-grid">
        <section className="panel employee-register-panel">
          <header className="chart-panel-heading"><div><span className="eyebrow">OPERATOR DIRECTORY</span><h2>Employee records</h2></div><span>{employees.length} employee{employees.length === 1 ? "" : "s"}</span></header>
          {employees.length ? (
            <div className="table-wrap"><table className="operator-table"><thead><tr><th>Employee</th><th>Assigned line</th><th>Status</th><th /></tr></thead><tbody>{employees.map((employee) => <tr key={employee.id}><td><strong>{employee.full_name}</strong><span className="table-subline">{employee.employee_code}</span></td><td>{employee.sewing_line}</td><td><ModeBadge mode={employee.active ? "ACTIVE" : "INACTIVE"} /></td><td><button type="button" className="icon-action" aria-label={`Edit ${employee.full_name}`} onClick={() => editEmployee(employee)}><Icon name="edit" size={16} /></button></td></tr>)}</tbody></table></div>
          ) : <EmptyState icon="users" title="No employees yet" description="Add each sewing operator and their assigned line using the form beside this table." />}
        </section>

        <form className="panel employee-form-panel" onSubmit={(event) => void saveEmployee(event)}>
          <div className="section-intro"><h2>{editingEmployee ? "Edit employee" : "Add an employee"}</h2><p>Assigned sewing lines automatically appear during session setup.</p></div>
          <label className="field-label" htmlFor="employee-code">Employee code</label>
          <input id="employee-code" className="form-input" placeholder="EMP-001" value={draft.employee_code} onChange={(event) => setDraft((current) => ({ ...current, employee_code: event.target.value }))} required />
          <label className="field-label" htmlFor="employee-name">Employee name</label>
          <input id="employee-name" className="form-input" placeholder="Full name" value={draft.full_name} onChange={(event) => setDraft((current) => ({ ...current, full_name: event.target.value }))} required />
          <label className="field-label" htmlFor="employee-line">Assigned sewing line</label>
          <input id="employee-line" className="form-input" placeholder="e.g. Sewing Line A" value={draft.sewing_line} onChange={(event) => setDraft((current) => ({ ...current, sewing_line: event.target.value }))} required />

          {editingEmployee ? <label className="approval-checkbox"><input type="checkbox" checked={draft.active ?? true} onChange={(event) => setDraft((current) => ({ ...current, active: event.target.checked }))} /><span>Employee is available for new production sessions.</span></label> : null}

          <div className="button-row">
            {editingEmployee ? <button type="button" className="action-button action-secondary" onClick={() => { setEditingEmployee(null); setDraft(emptyEmployee); }}>Cancel</button> : null}
            <button type="submit" className="action-button action-primary" disabled={saving}><Icon name={editingEmployee ? "check" : "plus"} size={16} />{saving ? "Saving…" : editingEmployee ? "Update employee" : "Add employee"}</button>
          </div>
        </form>
      </div>

      <div className="settings-section-heading"><span className="eyebrow">DEVICE MANAGEMENT</span><h2>Camera and operator controller</h2><p>Keep workstation devices ready for the next production session.</p></div>
      <DeviceSetupScreen configuration={configuration} readiness={readiness} activeSession={activeSession} onUpdated={onUpdated} embedded />

      <div className="settings-section-heading"><span className="eyebrow">PRODUCTION DATA</span><h2>Session history</h2><p>Manage locally stored garment counts, production sessions, and operator activity.</p></div>
      <section className="panel session-data-panel">
        <div className="session-data-overview">
          <span className="session-data-icon"><Icon name="database" size={20} /></span>
          <div>
            <h3>{sessions.length} saved production session{sessions.length === 1 ? "" : "s"}</h3>
            <p>Deleting history permanently removes session records, garment cycles, and their controller events. Employee records and device settings are kept.</p>
          </div>
        </div>
        {activeSession ? <InlineNotice tone="warning">End the active session before deleting production history.</InlineNotice> : null}
        <div className="session-data-actions">
          <span>Export any required records from Analytics before deleting them.</span>
          <button type="button" className="action-button action-danger" disabled={Boolean(activeSession) || sessions.length === 0} onClick={() => setDeleteDialogOpen(true)}>
            <Icon name="trash" size={15} /> Delete session data
          </button>
        </div>
      </section>

      {deleteDialogOpen ? (
        <div className="analytics-detail-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) closeDeleteDialog();
        }}>
          <section className="session-delete-modal" role="dialog" aria-modal="true" aria-labelledby="session-delete-title">
            <header className="session-delete-heading">
              <span className="session-delete-warning"><Icon name="warning" size={21} /></span>
              <button type="button" className="icon-action" aria-label="Close delete confirmation" disabled={deletingHistory} onClick={closeDeleteDialog}><Icon name="close" size={16} /></button>
            </header>
            <h2 id="session-delete-title">Delete all session history?</h2>
            <p>This permanently deletes {sessions.length} saved session{sessions.length === 1 ? "" : "s"}, all garment-cycle records, and all session-related controller events. This action cannot be undone.</p>
            <div className="session-delete-preserved"><Icon name="shield" size={16} /><span>Employees, sewing lines, camera settings, and controller configuration will not be deleted.</span></div>
            <form onSubmit={(event) => void deleteSessionHistory(event)}>
              <label className="field-label" htmlFor="delete-session-confirmation">Type <strong>{deleteConfirmationPhrase}</strong> to confirm</label>
              <input id="delete-session-confirmation" className="form-input" value={deleteConfirmation} autoComplete="off" spellCheck={false} disabled={deletingHistory} onChange={(event) => setDeleteConfirmation(event.target.value)} />
              <div className="button-row session-delete-buttons">
                <button type="button" className="action-button action-secondary" disabled={deletingHistory} onClick={closeDeleteDialog}>Keep session data</button>
                <button type="submit" className="action-button action-danger" disabled={deletingHistory || deleteConfirmation !== deleteConfirmationPhrase}><Icon name="trash" size={15} />{deletingHistory ? "Deleting…" : "Permanently delete"}</button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}
