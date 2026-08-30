import { useEffect, useState } from "react";
import { PowerOff, Wrench, Plus, VideoOff, CheckCircle2, XCircle, Loader2, Zap, Wrench as WrenchIcon } from "lucide-react";
import { fetchDowntime, submitDowntime, stopCamera, DowntimeEvent, DowntimeRecord } from "../lib/api";

const inputClass =
  "bg-surface border border-line rounded-lg px-3 py-2 text-ink text-sm font-mono w-full focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-shadow";
const labelClass = "text-ink-soft text-[10px] uppercase font-bold tracking-widest mb-1.5 block";

function toLocalInputValue(date: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function toLocalDateString(date: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export default function DowntimeLog() {
  const now = new Date();
  const [type, setType] = useState<DowntimeEvent["type"]>("breakdown");
  const [start, setStart] = useState(toLocalInputValue(now));
  const [end, setEnd] = useState(toLocalInputValue(now));
  const [reason, setReason] = useState("");
  const [events, setEvents] = useState<DowntimeRecord[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const [stoppingCamera, setStoppingCamera] = useState(false);
  const [cameraStopMessage, setCameraStopMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const handleStopCamera = async () => {
    setStoppingCamera(true);
    setCameraStopMessage(null);
    const result = await stopCamera();
    if (result.success) {
      setCameraStopMessage({
        ok: true,
        text: result.was_running ? "Camera turned off." : "Camera was already off.",
      });
    } else {
      setCameraStopMessage({ ok: false, text: result.error || "Could not turn off the camera." });
    }
    setStoppingCamera(false);
  };

  const loadEvents = async () => {
    const today = toLocalDateString(new Date());
    const data = await fetchDowntime(today);
    setEvents(data);
  };

  useEffect(() => {
    (async () => {
      await loadEvents();
    })();
  }, []);

  const handleSubmit = async () => {
    setError("");
    if (new Date(end) <= new Date(start)) {
      setError("End time must be after start time.");
      return;
    }
    setSubmitting(true);
    try {
      await submitDowntime({ type, start, end, reason });
      setReason("");
      await loadEvents();

      // A breakdown or power failure means the line isn't running - turn
      // the camera off automatically rather than leaving it open and idle.
      const result = await stopCamera();
      setCameraStopMessage(
        result.success
          ? { ok: true, text: result.was_running ? "Downtime logged. Camera turned off." : "Downtime logged." }
          : { ok: false, text: `Downtime logged, but could not turn off the camera: ${result.error}` }
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="w-full">
      <h1 className="text-ink text-2xl font-bold mb-1.5">Downtime Log</h1>
      <p className="text-ink-secondary text-[13px] mb-7">
        Track breakdowns and power failures, and control the capture camera while the line is stopped.
      </p>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-6 items-start">
      <div className="flex flex-col gap-6">
        <div className="bg-surface border border-line rounded-2xl p-6 flex flex-col gap-4 shadow-sm">
          <div className="flex items-center gap-2">
            <VideoOff size={16} className="text-ink-secondary" />
            <h3 className="text-ink font-bold text-sm uppercase tracking-widest">Camera Control</h3>
          </div>
          <p className="text-ink-soft text-[12.5px]">
            Turn off the camera that's currently open and running - e.g. while the line is stopped for a
            breakdown or power failure. Reopen it any time from Device Setup.
          </p>
          <button
            onClick={handleStopCamera}
            disabled={stoppingCamera}
            className="flex items-center gap-2 px-4 py-2.5 bg-ink text-white hover:bg-ink/90 rounded-lg text-[13px] font-medium transition-colors disabled:opacity-50 w-fit shadow-sm"
          >
            {stoppingCamera ? <Loader2 size={15} className="animate-spin" /> : <VideoOff size={15} />}
            {stoppingCamera ? "Turning off..." : "Turn Off Camera"}
          </button>
          {cameraStopMessage && (
            <div className={`flex items-center gap-2 text-[12px] ${cameraStopMessage.ok ? "text-success" : "text-error"}`}>
              {cameraStopMessage.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
              {cameraStopMessage.text}
            </div>
          )}
        </div>

        <div className="bg-surface border border-line rounded-2xl p-6 flex flex-col gap-6 shadow-sm">
          <div className="flex items-center gap-2">
            <PowerOff size={16} className="text-error" />
            <h3 className="text-ink font-bold text-sm uppercase tracking-widest">Log Downtime</h3>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Type</label>
              <select className={inputClass} value={type} onChange={(e) => setType(e.target.value as DowntimeEvent["type"])}>
                <option value="breakdown">Machine Breakdown</option>
                <option value="power_failure">Power Failure</option>
              </select>
            </div>
            <div />
            <div>
              <label className={labelClass}>Start</label>
              <input type="datetime-local" className={inputClass} value={start} onChange={(e) => setStart(e.target.value)} />
            </div>
            <div>
              <label className={labelClass}>End</label>
              <input type="datetime-local" className={inputClass} value={end} onChange={(e) => setEnd(e.target.value)} />
            </div>
            <div className="col-span-2">
              <label className={labelClass}>Reason</label>
              <input
                type="text"
                className={inputClass}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Sewing machine motor failure"
              />
            </div>
          </div>

          {error && <div className="text-[12px] text-error">{error}</div>}

          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="flex items-center gap-2 px-4 py-2.5 bg-error text-white hover:bg-error/90 rounded-lg text-[13px] font-medium transition-colors disabled:opacity-50 w-fit shadow-sm"
          >
            <Plus size={15} /> {submitting ? "Logging..." : "Log Event"}
          </button>
        </div>
      </div>

      <div className="bg-surface border border-line rounded-2xl shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-line-soft flex items-center gap-2">
          <Wrench size={16} className="text-accent" />
          <h3 className="text-ink font-semibold text-[13px] uppercase tracking-wide">Today's Downtime Events</h3>
        </div>
        <div className="flex flex-col divide-y divide-line-soft max-h-[560px] overflow-y-auto">
          {events.length === 0 ? (
            <div className="p-8 text-center text-ink-soft font-mono text-xs">No downtime logged today.</div>
          ) : (
            events.map((ev) => (
              <div key={ev._id} className="px-6 py-4 flex items-start gap-3">
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                    ev.type === "power_failure" ? "bg-warning-soft text-warning" : "bg-error-soft text-error"
                  }`}
                >
                  {ev.type === "power_failure" ? <Zap size={15} /> : <WrenchIcon size={15} />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className={`text-[13px] font-semibold ${ev.type === "power_failure" ? "text-warning" : "text-error"}`}>
                    {ev.type === "power_failure" ? "Power Failure" : "Machine Breakdown"}
                  </div>
                  <div className="text-ink-soft text-[11px] font-mono mt-0.5">
                    {new Date(ev.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} -{" "}
                    {new Date(ev.end).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </div>
                  {ev.reason && <div className="text-ink-secondary text-[12px] mt-1 truncate">{ev.reason}</div>}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
      </div>
    </div>
  );
}
