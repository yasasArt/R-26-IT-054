import { useEffect, useMemo, useState } from "react";
import { Settings as SettingsIcon, Save, Plus, Trash2, Calculator, Database, AlertTriangle, Loader2, CheckCircle2, X } from "lucide-react";
import {
  fetchSettings,
  updateSettings,
  deleteAllGarments,
  Settings,
  BreakWindow,
  CATEGORIES,
  CATEGORY_LABEL,
} from "../lib/api";

const EMPTY_SETTINGS: Settings = {
  target_pieces: 100,
  category_targets: { SHIRT: 0, T_SHIRT: 0, TROUSER: 0, SHORT: 0 },
  start_date: new Date().toISOString().slice(0, 10),
  due_date: new Date().toISOString().slice(0, 10),
  work_start_time: "08:00",
  work_end_time: "18:00",
  breaks: [
    { name: "Tea Break", start_time: "10:00", duration_minutes: 15 },
    { name: "Lunch Break", start_time: "12:30", duration_minutes: 45 },
  ],
};

const inputClass =
  "bg-surface border border-line rounded-lg px-3 py-2 text-ink text-sm font-mono w-full focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-shadow";
const labelClass = "text-ink-soft text-[10px] uppercase font-bold tracking-widest mb-1.5 block";

function parseHHMM(value: string): number {
  const [h, m] = value.split(":").map(Number);
  return (h || 0) + (m || 0) / 60;
}

interface SettingsPanelProps {
  onSaved?: () => void;
  historyCount?: number;
  onHistoryDeleted?: () => void;
}

export default function SettingsPanel({ onSaved, historyCount = 0, onHistoryDeleted }: SettingsPanelProps) {
  const [form, setForm] = useState<Settings>(EMPTY_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState("");

  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteResult, setDeleteResult] = useState<{ ok: boolean; text: string } | null>(null);

  const handleDeleteAllHistory = async () => {
    setDeleting(true);
    setDeleteResult(null);
    try {
      const result = await deleteAllGarments();
      setDeleteResult({ ok: true, text: `Deleted ${result.deleted_count} history record${result.deleted_count === 1 ? "" : "s"}.` });
      onHistoryDeleted?.();
    } catch (error) {
      setDeleteResult({ ok: false, text: error instanceof Error ? error.message : String(error) });
    } finally {
      setDeleting(false);
      setConfirmingDelete(false);
    }
  };

  useEffect(() => {
    (async () => {
      const current = await fetchSettings();
      if (current) setForm(current);
      setLoading(false);
    })();
  }, []);

  const updateBreak = (index: number, field: keyof BreakWindow, value: string | number) => {
    const breaks = [...form.breaks];
    breaks[index] = { ...breaks[index], [field]: value };
    setForm({ ...form, breaks });
  };

  const addBreak = () => {
    setForm({ ...form, breaks: [...form.breaks, { name: "New Break", start_time: "09:00", duration_minutes: 10 }] });
  };

  const removeBreak = (index: number) => {
    setForm({ ...form, breaks: form.breaks.filter((_, i) => i !== index) });
  };

  const handleSubmit = async () => {
    setSaving(true);
    setSavedMsg("");
    try {
      await updateSettings(form);
      // Saving always resets count_since to now on the backend (that's what
      // makes Total Packed/Efficiency read as 0 for the new counting cycle) -
      // refetch so the form picks up that server-computed value rather than
      // just trusting whatever was locally held.
      const fresh = await fetchSettings();
      if (fresh) setForm(fresh);
      setSavedMsg("Saved successfully. Dashboard has been reset for the new target.");
      onSaved?.();
    } catch (error) {
      setSavedMsg(`Failed to save: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setSaving(false);
    }
  };

  const updateCategoryTarget = (category: (typeof CATEGORIES)[number], value: number) => {
    setForm({ ...form, category_targets: { ...form.category_targets, [category]: value } });
  };

  const categoryTargetSum = useMemo(
    () => CATEGORIES.reduce((sum, cat) => sum + (form.category_targets?.[cat] ?? 0), 0),
    [form.category_targets]
  );

  const summary = useMemo(() => {
    const startDate = new Date(form.start_date);
    startDate.setHours(0, 0, 0, 0);
    const totalDays = Math.max(1, Math.round((new Date(form.due_date).getTime() - startDate.getTime()) / 86400000));
    const scheduledHours = Math.max(0, parseHHMM(form.work_end_time) - parseHHMM(form.work_start_time));
    const breakHours = form.breaks.reduce((sum, b) => sum + b.duration_minutes, 0) / 60;
    const plannedDailyHours = Math.max(0, scheduledHours - breakHours);
    const totalHoursAllocated = totalDays * plannedDailyHours;
    const requiredRatePerHour = totalHoursAllocated > 0 ? form.target_pieces / totalHoursAllocated : 0;
    return { totalDays, plannedDailyHours, totalHoursAllocated, requiredRatePerHour };
  }, [form]);

  if (loading) {
    return <div className="text-ink-soft font-mono text-xs p-5">Loading settings...</div>;
  }

  return (
    <div className="w-full">
      <h1 className="text-ink text-2xl font-bold mb-1.5">Target &amp; Schedule</h1>
      <p className="text-ink-secondary text-[13px] mb-7">
        Set the production target, due date, and shift schedule used for decision-support forecasting.
      </p>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6 items-start">
      <div className="bg-surface border border-line rounded-2xl shadow-sm p-7 flex flex-col gap-6">
        <div className="flex items-center gap-2">
          <SettingsIcon size={16} className="text-accent" />
          <h3 className="text-ink font-bold text-sm uppercase tracking-widest">Production Target &amp; Schedule</h3>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div>
            <label className={labelClass}>Total Target</label>
            <input
              type="number"
              className={inputClass}
              value={form.target_pieces}
              onChange={(e) => setForm({ ...form, target_pieces: Number(e.target.value) })}
            />
          </div>
          <div>
            <label className={labelClass}>Started</label>
            <input
              type="date"
              className={inputClass}
              value={form.start_date}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            />
          </div>
          <div>
            <label className={labelClass}>Due Date</label>
            <input
              type="date"
              className={inputClass}
              value={form.due_date}
              onChange={(e) => setForm({ ...form, due_date: e.target.value })}
            />
          </div>
          <div>
            <label className={labelClass}>Shift Start</label>
            <input
              type="time"
              className={inputClass}
              value={form.work_start_time}
              onChange={(e) => setForm({ ...form, work_start_time: e.target.value })}
            />
          </div>
          <div>
            <label className={labelClass}>Shift End</label>
            <input
              type="time"
              className={inputClass}
              value={form.work_end_time}
              onChange={(e) => setForm({ ...form, work_end_time: e.target.value })}
            />
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <label className={labelClass + " mb-0"}>Category Targets</label>
            <span className={`text-[11px] font-mono ${categoryTargetSum === form.target_pieces ? "text-ink-soft" : "text-warning"}`}>
              Sum: {categoryTargetSum} / {form.target_pieces}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {CATEGORIES.map((category) => (
              <div key={category}>
                <label className={labelClass}>{CATEGORY_LABEL[category]}</label>
                <input
                  type="number"
                  className={inputClass}
                  value={form.category_targets?.[category] ?? 0}
                  onChange={(e) => updateCategoryTarget(category, Number(e.target.value))}
                />
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <label className={labelClass + " mb-0"}>Fixed Daily Breaks (Tea / Lunch)</label>
            <button
              onClick={addBreak}
              className="flex items-center gap-1 text-[10px] font-mono text-accent hover:text-accent/80 uppercase font-bold"
            >
              <Plus size={12} /> Add
            </button>
          </div>

          {form.breaks.map((b, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type="text"
                className={inputClass + " flex-1"}
                value={b.name}
                onChange={(e) => updateBreak(i, "name", e.target.value)}
                placeholder="Break name"
              />
              <input
                type="time"
                className={inputClass + " w-32"}
                value={b.start_time}
                onChange={(e) => updateBreak(i, "start_time", e.target.value)}
              />
              <input
                type="number"
                className={inputClass + " w-24"}
                value={b.duration_minutes}
                onChange={(e) => updateBreak(i, "duration_minutes", Number(e.target.value))}
                placeholder="mins"
              />
              <button onClick={() => removeBreak(i)} className="text-ink-soft hover:text-error p-2">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>

        <div className="flex items-start gap-2.5 text-[12px] text-warning bg-warning-soft px-3.5 py-2.5 rounded-lg">
          <AlertTriangle size={14} className="flex-shrink-0 mt-0.5" />
          Saving starts a new target: Total Packed and Efficiency on the dashboard reset to 0 and count fresh from
          today. Past history is kept and still visible in History Log/Analytics.
        </div>

        <div className="flex items-center gap-4 pt-2">
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2.5 bg-accent text-white hover:bg-accent/90 rounded-lg text-[13px] font-semibold transition-colors disabled:opacity-50 shadow-sm"
          >
            <Save size={14} /> {saving ? "Saving..." : "Save Settings"}
          </button>
          {savedMsg && <span className="text-[12px] text-ink-secondary">{savedMsg}</span>}
        </div>
      </div>

      <div className="bg-surface border border-line rounded-2xl shadow-sm p-6">
        <div className="flex items-center gap-2 mb-5">
          <Calculator size={16} className="text-accent" />
          <h3 className="text-ink font-semibold text-[13px] uppercase tracking-wide">Schedule Summary</h3>
        </div>
        <div className="flex flex-col gap-4">
          <div>
            <div className="text-ink-soft text-[10px] uppercase font-bold tracking-widest mb-1">Days Allocated</div>
            <div className="font-mono text-xl font-bold text-ink">{summary.totalDays} days</div>
          </div>
          <div>
            <div className="text-ink-soft text-[10px] uppercase font-bold tracking-widest mb-1">Effective Hours / Day</div>
            <div className="font-mono text-xl font-bold text-ink">{summary.plannedDailyHours.toFixed(1)} hrs</div>
            <div className="text-ink-soft text-[11px] mt-0.5">Shift hours minus fixed breaks</div>
          </div>
          <div>
            <div className="text-ink-soft text-[10px] uppercase font-bold tracking-widest mb-1">Total Hours Allocated</div>
            <div className="font-mono text-xl font-bold text-ink">{summary.totalHoursAllocated.toFixed(1)} hrs</div>
          </div>
          <div className="pt-3 border-t border-line-soft">
            <div className="text-ink-soft text-[10px] uppercase font-bold tracking-widest mb-1">Required Pace</div>
            <div className="font-mono text-xl font-bold text-accent">{summary.requiredRatePerHour.toFixed(2)} pcs/hr</div>
            <div className="text-ink-soft text-[11px] mt-0.5">To hit the target by the due date</div>
          </div>
        </div>
      </div>
      </div>

      <div className="bg-surface border border-line rounded-2xl shadow-sm p-7 mt-6">
        <div className="flex items-center gap-2 mb-2">
          <Database size={16} className="text-error" />
          <h3 className="text-ink font-bold text-sm uppercase tracking-widest">History Management</h3>
        </div>
        <p className="text-ink-secondary text-[13px] mb-5">
          Permanently delete saved detection history from the database. This does not affect your target/schedule
          settings or downtime records.
        </p>

        <div className="text-ink-soft text-[12.5px] mb-4">
          <span className="font-mono font-bold text-ink">{historyCount}</span> record{historyCount === 1 ? "" : "s"} currently
          saved.
        </div>

        {!confirmingDelete ? (
          <button
            onClick={() => {
              setConfirmingDelete(true);
              setDeleteResult(null);
            }}
            disabled={historyCount === 0}
            className="flex items-center gap-2 px-4 py-2.5 bg-error text-white hover:bg-error/90 rounded-lg text-[13px] font-medium transition-colors disabled:opacity-50 w-fit shadow-sm"
          >
            <Trash2 size={15} /> Delete All History
          </button>
        ) : (
          <div className="bg-error-soft border border-error/20 rounded-xl p-5 flex flex-col gap-4">
            <div className="flex items-start gap-2.5 text-error text-[13px]">
              <AlertTriangle size={18} className="flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold">
                  Delete all {historyCount} history record{historyCount === 1 ? "" : "s"}?
                </div>
                <div className="text-ink-secondary mt-1">
                  This permanently removes every saved detection record from the database. This cannot be undone.
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleDeleteAllHistory}
                disabled={deleting}
                className="flex items-center gap-2 px-4 py-2.5 bg-error text-white hover:bg-error/90 rounded-lg text-[13px] font-semibold transition-colors disabled:opacity-50 shadow-sm"
              >
                {deleting ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />}
                {deleting ? "Deleting..." : "Yes, Delete Everything"}
              </button>
              <button
                onClick={() => setConfirmingDelete(false)}
                disabled={deleting}
                className="flex items-center gap-2 px-4 py-2.5 bg-surface text-ink hover:bg-surface-muted border border-line rounded-lg text-[13px] font-medium transition-colors disabled:opacity-50"
              >
                <X size={15} /> Cancel
              </button>
            </div>
          </div>
        )}

        {deleteResult && (
          <div
            className={`flex items-center gap-2.5 text-[13px] mt-4 px-4 py-3 rounded-lg ${
              deleteResult.ok ? "text-success bg-success-soft" : "text-error bg-error-soft"
            }`}
          >
            {deleteResult.ok ? <CheckCircle2 size={16} className="flex-shrink-0" /> : <AlertTriangle size={16} className="flex-shrink-0" />}
            {deleteResult.text}
          </div>
        )}
      </div>
    </div>
  );
}
