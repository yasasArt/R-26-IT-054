"use client";

import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, TimerReset } from "lucide-react";
import { useSewingSimulator } from "@/lib/hooks/useSewingSimulator";
import { CYCLE_TIME } from "@/lib/constants";
import { formatDuration, formatTime } from "@/lib/utils";
import { useSewingStore } from "@/store/sewingStore";
import { useWorkstationStore } from "@/store/workstationStore";
import { CameraFrame, DataTable, MetricCard, MiniBarChart, PageHeader, Panel, StatusPill } from "@/components/industrial/Primitives";

export default function SewingDashboardPage() {
  useSewingSimulator("1x");

  const { config } = useWorkstationStore();
  const sewing = useSewingStore();
  const progress = Math.min(Math.round((sewing.pieceCount / config.shiftTarget) * 100), 100);
  const recentCycles = sewing.cycleHistory.slice(-12).map(item => item.durationSeconds);
  const currentTone = sewing.currentCycleTimeSeconds <= CYCLE_TIME.TARGET_SECONDS ? "ok" : sewing.currentCycleTimeSeconds <= CYCLE_TIME.WARNING_SECONDS ? "warn" : "bad";

  return (
    <div className="animate-in">
      <PageHeader
        eyebrow="Feature 2 | Sewing operator area"
        title="Live production monitor"
        description="Camera-based output zone monitoring with dual-signal piece counting, operator cycle-time analysis, and IoT-driven rework/downtime handling."
        actions={<StatusPill label="Simulated live feed" tone="ok" pulse />}
      />

      <div className="grid grid-4">
        <MetricCard label="Total pieces" value={sewing.pieceCount} sub={`${config.shiftTarget} pcs shift target`} tone="ok" badge={`${progress}%`} />
        <MetricCard label="Current cycle" value={sewing.currentCycleTimeSeconds || "—"} unit={sewing.currentCycleTimeSeconds ? "s" : ""} sub={`Target ${CYCLE_TIME.TARGET_SECONDS}s`} tone={currentTone} />
        <MetricCard label="Average cycle" value={sewing.averageCycleTimeSeconds ? sewing.averageCycleTimeSeconds.toFixed(1) : "—"} unit="s" sub="Rolling detected pieces" tone="info" />
        <MetricCard label="Downtime" value={formatDuration(sewing.totalDowntimeSeconds)} sub={`${sewing.totalReworkCount} rework events`} tone={sewing.downtimeActive ? "bad" : "muted"} badge={sewing.operatorStatus} />
      </div>

      <div className="grid monitor-grid" style={{ marginTop: 16 }}>
        <Panel title="Output Zone Camera" eyebrow="YOLOv8 + pose verification" action={<StatusPill label={sewing.cameraStatus} tone="ok" pulse />}>
          <CameraFrame mode="sewing">
            <div style={{ position: "absolute", inset: "82px 18% 72px", border: "2px solid rgba(37, 192, 109, 0.55)", borderRadius: 14 }} />
            <div style={{ position: "absolute", left: "22%", top: "42%" }}><StatusPill label="Garment stationary" tone={sewing.dualSignal.signalA === "triggered" ? "ok" : "muted"} /></div>
            <div style={{ position: "absolute", right: "18%", top: "58%" }}><StatusPill label="Wrist withdrew" tone={sewing.dualSignal.signalB === "triggered" ? "ok" : "muted"} /></div>
            <div className="camera-caption">
              <StatusPill label={`Signal A ${sewing.dualSignal.signalA}`} tone={sewing.dualSignal.signalA === "triggered" ? "ok" : "muted"} />
              <StatusPill label={`Signal B ${sewing.dualSignal.signalB}`} tone={sewing.dualSignal.signalB === "triggered" ? "ok" : "muted"} />
              <StatusPill label={sewing.dualSignal.bothAgreed ? "Count authorised" : "Awaiting agreement"} tone={sewing.dualSignal.bothAgreed ? "ok" : "info"} />
            </div>
          </CameraFrame>
        </Panel>

        <div className="grid">
          <Panel title="Operator State" eyebrow="Cycle behavior" action={<StatusPill label={sewing.operatorStatus} tone={sewing.operatorStatus === "active" ? "ok" : sewing.operatorStatus === "downtime" ? "bad" : "warn"} />}>
            <div className="panel-body grid grid-2">
              <ActionState icon={<CheckCircle2 size={20} />} label="Counting model" value="Ready" tone="ok" />
              <ActionState icon={<TimerReset size={20} />} label="Cycle timer" value={sewing.currentCycleTimeSeconds ? `${sewing.currentCycleTimeSeconds}s` : "Waiting"} tone="info" />
              <ActionState icon={<AlertTriangle size={20} />} label="Rework" value={sewing.reworkActive ? "Active" : "Clear"} tone={sewing.reworkActive ? "warn" : "ok"} />
              <ActionState icon={<AlertTriangle size={20} />} label="Downtime" value={sewing.downtimeActive ? "Active" : "Clear"} tone={sewing.downtimeActive ? "bad" : "ok"} />
            </div>
          </Panel>

          <Panel title="IoT Device" eyebrow="ESP32 actions" action={<StatusPill label={sewing.iotStatus} tone={sewing.iotStatus === "connected" ? "ok" : "bad"} />}>
            <div className="panel-body grid grid-2">
              <button className="btn" onClick={sewing.reworkActive ? sewing.endRework : sewing.startRework}>{sewing.reworkActive ? "Resolve Rework" : "Trigger Rework"}</button>
              <button className="btn btn-danger" onClick={sewing.downtimeActive ? sewing.endDowntime : sewing.startDowntime}>{sewing.downtimeActive ? "Resolve Downtime" : "Trigger Downtime"}</button>
            </div>
          </Panel>
        </div>
      </div>

      <div className="grid grid-3" style={{ marginTop: 16 }}>
        <Panel title="Cycle Time Trend" eyebrow="Last 12 detections" className="span-2">
          <div className="panel-body">
            <MiniBarChart values={recentCycles.length ? recentCycles : [42, 44, 39, 51, 46, 43, 48, 55]} tone="cyan" />
          </div>
        </Panel>
        <Panel title="Shift Summary" eyebrow="Local session">
          <div className="panel-body grid">
            <SummaryRow label="Target completion" value={`${progress}%`} />
            <SummaryRow label="Pieces remaining" value={Math.max(config.shiftTarget - sewing.pieceCount, 0)} />
            <SummaryRow label="Camera channel" value={config.cameraId} />
            <SummaryRow label="Station" value={config.stationId} />
          </div>
        </Panel>
      </div>

      <div style={{ marginTop: 16 }}>
        <Panel title="Recent Piece Detection Log" eyebrow="Dual-signal accepted events">
          <DataTable
            headers={["Time", "Piece", "Cycle", "Confidence", "Operator", "Signals"]}
            rows={sewing.detectionLog.slice(0, 9).map(event => [
              formatTime(new Date(event.timestamp)),
              `#${event.pieceNumber}`,
              `${event.cycleTimeSeconds}s`,
              `${Math.round(event.confidenceScore * 100)}%`,
              event.operatorStatus,
              event.signalA && event.signalB ? <StatusPill key="ok" label="A+B" tone="ok" /> : <StatusPill key="wait" label="Pending" tone="warn" />,
            ])}
          />
        </Panel>
      </div>
    </div>
  );
}

function ActionState({ icon, label, value, tone }: { icon: ReactNode; label: string; value: string; tone: "ok" | "warn" | "bad" | "info" }) {
  return (
    <div className="panel" style={{ boxShadow: "none", padding: 14 }}>
      <div className={tone}>{icon}</div>
      <div className="meta-label" style={{ marginTop: 8 }}>{label}</div>
      <strong>{value}</strong>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, borderBottom: "1px solid var(--line-soft)", paddingBottom: 10 }}>
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
