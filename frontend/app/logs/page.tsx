"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { DataTable, MetricCard, PageHeader, Panel, StatusPill } from "@/components/industrial/Primitives";
import { formatDuration, formatTime } from "@/lib/utils";
import { Timer } from "lucide-react";
import { useQualityStore } from "@/store/qualityStore";
import { useSewingStore } from "@/store/sewingStore";
import { useWorkstationStore } from "@/store/workstationStore";

export default function LogsPage() {
  return (
    <DashboardShell>
      <LogsContent />
    </DashboardShell>
  );
}

function LogsContent() {
  const { config } = useWorkstationStore();
  const sewing = useSewingStore();
  const quality = useQualityStore();
  const isQuality = config.mode === "quality";
  const rows = isQuality ? buildQualityRows(quality.inspectionLog) : buildSewingRows(sewing.detectionLog, sewing.iotEvents);
  const latestSewing = sewing.detectionLog[0];
  const latestQuality = quality.inspectionLog[0];
  const nowMs = useNowMs(sewing.downtimeActive);
  const downtimeCycles = buildDowntimeCycles(sewing.iotEvents, sewing.downtimeActive, sewing.downtimeStartTime, nowMs);
  const reworkCycles = sewing.totalReworkCount + (sewing.reworkActive ? 1 : 0);
  const activeDowntimeSeconds = sewing.downtimeActive && sewing.downtimeStartTime ? Math.max(Math.floor((nowMs - new Date(sewing.downtimeStartTime).getTime()) / 1000), 0) : 0;
  const totalDowntime = sewing.totalDowntimeSeconds + activeDowntimeSeconds;
  const supervisorRows = isQuality ? [] : buildSupervisorRows(sewing.detectionLog, sewing.iotEvents, sewing.reworkActive, sewing.reworkStartTime, sewing.downtimeActive, sewing.downtimeStartTime, nowMs);

  return (
    <div className="animate-in">
      <PageHeader
        eyebrow="Logs & history"
        title="Local production records"
        description="A compact history view for the currently configured workstation mode. These records are simulated locally and shaped for future local API persistence."
        actions={<StatusPill label={isQuality ? "Quality logs" : "Sewing logs"} tone="info" />}
      />
      <div className="grid grid-4">
        <MetricCard label="Mode" value={isQuality ? "Quality" : "Sewing"} sub={config.stationId} tone="info" />
        <MetricCard label={isQuality ? "Inspections" : "Piece counts"} value={isQuality ? quality.inspectionLog.length : sewing.detectionLog.length} sub={isQuality ? `${quality.approvedCount} pass, ${quality.reworkCount} rework` : `${sewing.pieceCount} total pieces`} tone="ok" />
        <MetricCard label={isQuality ? "Latest decision" : "Operator actions"} value={isQuality ? latestQuality?.decision || "—" : reworkCycles + downtimeCycles.length} sub={isQuality ? "Garment records" : `${reworkCycles} rework, ${downtimeCycles.length} downtime cycles`} tone="cyan" />
        <MetricCard label="Operator" value={config.operatorName || "—"} sub="Active session" tone="muted" />
      </div>
      {!isQuality && (
        <div className="grid grid-3" style={{ marginTop: 16 }}>
          <Panel title="Sewing Log Totals" eyebrow="Current workstation state">
            <div className="stat-list">
              <SummaryRow label="Pieces counted" value={sewing.pieceCount} />
              <SummaryRow label="Rework cycles" value={reworkCycles} />
              <SummaryRow label="Downtime cycles" value={downtimeCycles.length} />
              <SummaryRow label="Total downtime" value={formatDuration(totalDowntime)} />
            </div>
          </Panel>
          <Panel title="Downtime History Chart" eyebrow="Most recent downtime durations" className="span-2">
            <DowntimeLogChart cycles={downtimeCycles} />
          </Panel>
        </div>
      )}
      <div className="grid grid-3" style={{ marginTop: 16 }}>
        <Panel title="Current Log Summary" eyebrow={isQuality ? "Inspection details" : "Sewing details"}>
          <div className="stat-list">
            {isQuality ? (
              <>
                <SummaryRow label="Latest record" value={latestQuality ? formatTime(new Date(latestQuality.timestamp)) : "No inspections yet"} />
                <SummaryRow label="Latest spec" value={latestQuality?.specLabel || "—"} />
                <SummaryRow label="Latest confidence" value={latestQuality ? `${Math.round(latestQuality.garmentAnalysis.overallConfidence * 100)}%` : "—"} />
              </>
            ) : (
              <>
                <SummaryRow label="Latest count" value={latestSewing ? `Piece #${latestSewing.pieceNumber}` : "No pieces yet"} />
                <SummaryRow label="Latest cycle" value={latestSewing ? `${latestSewing.cycleTimeSeconds}s` : "—"} />
                <SummaryRow label="Operator action cycles" value={reworkCycles + downtimeCycles.length} />
              </>
            )}
          </div>
        </Panel>
        <Panel title="How To Read" eyebrow="For supervisors">
          <div className="stat-list">
            <SummaryRow label="Green" value="Normal / accepted" />
            <SummaryRow label="Yellow" value="Needs attention" />
            <SummaryRow label="Red" value="Problem event" />
          </div>
        </Panel>
        <Panel title="Storage Note" eyebrow="Prototype data">
          <div className="stat-list">
            <SummaryRow label="Source" value="Local browser state" />
            <SummaryRow label="Order" value="Newest first" />
            <SummaryRow label="Backend" value="Ready for API sync" />
          </div>
        </Panel>
      </div>
      {!isQuality && (
        <div style={{ marginTop: 16 }}>
          <Panel title="Supervisor Sewing Log" eyebrow="Shift review notes">
            <DataTable
              headers={["Time", "Supervisor note", "Production impact", "Duration / cycle", "Review status"]}
              rows={supervisorRows}
              emptyMessage="No supervisor log entries yet. Add pieces or operator actions from the demo panel."
            />
          </Panel>
        </div>
      )}
      <div style={{ marginTop: 16 }}>
        <Panel title={isQuality ? "Inspection History" : "Sewing Event History"} eyebrow="Most recent first with full details">
          <DataTable headers={["Time", "Event", "Main detail", "Measured value", "Status", "Source / confidence"]} rows={rows} emptyMessage="No history records yet. Use the live monitor or demo panel to create events." />
        </Panel>
      </div>
    </div>
  );
}

function buildSewingRows(detections: ReturnType<typeof useSewingStore.getState>["detectionLog"], iotEvents: ReturnType<typeof useSewingStore.getState>["iotEvents"]) {
  const detectionRows = detections.map(item => ({
    time: new Date(item.timestamp),
    row: [
      formatTime(new Date(item.timestamp)),
      "Piece count accepted",
      `Piece #${item.pieceNumber} counted after both camera signals agreed.`,
      `${item.cycleTimeSeconds}s cycle time`,
      <StatusPill key={item.id} label={item.cycleTimeSeconds <= 45 ? "On target" : item.cycleTimeSeconds <= 65 ? "Slow" : "Very slow"} tone={item.cycleTimeSeconds <= 45 ? "ok" : item.cycleTimeSeconds <= 65 ? "warn" : "bad"} />,
      `Camera confidence ${Math.round(item.confidenceScore * 100)}% · Signals A:${item.signalA ? "yes" : "no"} B:${item.signalB ? "yes" : "no"}`,
    ] as ReactNode[],
  }));

  const actionRows = iotEvents.map(item => ({
    time: new Date(item.timestamp),
    row: [
      formatTime(new Date(item.timestamp)),
      item.type.includes("rework") ? "Rework button" : "Downtime button",
      labelIoTEvent(item.type),
      item.durationSeconds !== undefined ? formatDuration(item.durationSeconds) : "Started",
      <StatusPill key={item.id} label={item.type.includes("resolved") ? "Cycle closed" : "Cycle started"} tone={item.type.includes("resolved") ? "ok" : item.type.includes("rework") ? "warn" : "bad"} />,
      `Triggered by ${item.triggeredBy}`,
    ] as ReactNode[],
  }));

  return [...detectionRows, ...actionRows]
    .sort((a, b) => b.time.getTime() - a.time.getTime())
    .slice(0, 24)
    .map(item => item.row);
}

function buildSupervisorRows(
  detections: ReturnType<typeof useSewingStore.getState>["detectionLog"],
  iotEvents: ReturnType<typeof useSewingStore.getState>["iotEvents"],
  reworkActive: boolean,
  reworkStartTime: Date | null,
  downtimeActive: boolean,
  downtimeStartTime: Date | null,
  nowMs: number
) {
  const pieceRows = detections.slice(0, 8).map((item) => {
    const slow = item.cycleTimeSeconds > 65;
    const watch = item.cycleTimeSeconds > 45 && item.cycleTimeSeconds <= 65;
    return {
      time: new Date(item.timestamp),
      row: [
        formatTime(new Date(item.timestamp)),
        `Piece #${item.pieceNumber} accepted for production count.`,
        slow ? "Cycle time above limit" : watch ? "Cycle needs observation" : "Normal output",
        `${item.cycleTimeSeconds}s cycle`,
        <StatusPill key={item.id} label={slow ? "Review" : watch ? "Watch" : "Accepted"} tone={slow ? "bad" : watch ? "warn" : "ok"} />,
      ] as ReactNode[],
    };
  });

  const resolvedActionRows = iotEvents
    .filter((item) => item.type === "rework_resolved" || item.type === "downtime_resolved")
    .slice(0, 8)
    .map((item) => {
      const isDowntime = item.type === "downtime_resolved";
      return {
        time: new Date(item.timestamp),
        row: [
          formatTime(new Date(item.timestamp)),
          isDowntime ? "Downtime cycle closed by operator." : "Rework cycle closed by operator.",
          isDowntime ? "Machine availability affected" : "Piece required correction",
          formatDuration(item.durationSeconds ?? 0),
          <StatusPill key={item.id} label={isDowntime ? "Downtime closed" : "Rework closed"} tone={isDowntime ? "bad" : "warn"} />,
        ] as ReactNode[],
      };
    });

  const activeRows = [
    reworkActive && reworkStartTime
      ? {
          time: new Date(reworkStartTime),
          row: [
            formatTime(new Date(reworkStartTime)),
            "Rework is currently active.",
            "Supervisor follow-up required",
            formatDuration(Math.max(Math.floor((nowMs - new Date(reworkStartTime).getTime()) / 1000), 0)),
            <StatusPill key="active-rework" label="Active" tone="warn" pulse />,
          ] as ReactNode[],
        }
      : null,
    downtimeActive && downtimeStartTime
      ? {
          time: new Date(downtimeStartTime),
          row: [
            formatTime(new Date(downtimeStartTime)),
            "Downtime is currently active.",
            "Output stopped",
            formatDuration(Math.max(Math.floor((nowMs - new Date(downtimeStartTime).getTime()) / 1000), 0)),
            <StatusPill key="active-downtime" label="Active" tone="bad" pulse />,
          ] as ReactNode[],
        }
      : null,
  ].filter((item): item is { time: Date; row: ReactNode[] } => item !== null);

  return [...activeRows, ...resolvedActionRows, ...pieceRows]
    .sort((a, b) => b.time.getTime() - a.time.getTime())
    .slice(0, 14)
    .map((item) => item.row);
}

type SewingIoTEvent = ReturnType<typeof useSewingStore.getState>["iotEvents"][number];
type DowntimeCycle = { id: string; startedAt: Date; durationSeconds: number; status: "active" | "closed" };

function useNowMs(active: boolean) {
  const [nowMs, setNowMs] = useState(0);

  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [active]);

  return nowMs;
}

function buildDowntimeCycles(events: SewingIoTEvent[], downtimeActive: boolean, downtimeStartTime: Date | null, nowMs: number): DowntimeCycle[] {
  const cycles: DowntimeCycle[] = [];
  const resolved = [...events]
    .filter((event) => event.type === "downtime_resolved")
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  if (downtimeActive && downtimeStartTime) {
    cycles.push({
      id: "active-downtime",
      startedAt: new Date(downtimeStartTime),
      durationSeconds: Math.max(Math.floor((nowMs - new Date(downtimeStartTime).getTime()) / 1000), 0),
      status: "active",
    });
  }

  resolved.forEach((event) => {
    cycles.push({ id: event.id, startedAt: new Date(event.timestamp), durationSeconds: event.durationSeconds ?? 0, status: "closed" });
  });

  return cycles.slice(0, 8);
}

function DowntimeLogChart({ cycles }: { cycles: DowntimeCycle[] }) {
  const max = Math.max(...cycles.map((cycle) => cycle.durationSeconds), 60);

  if (!cycles.length) {
    return (
      <div className="empty-chart">
        <Timer size={18} />
        <span>No downtime records yet. Trigger and resolve downtime from the demo panel to create chart data.</span>
      </div>
    );
  }

  return (
    <div className="chart-panel downtime-chart">
      <div className="downtime-list-chart" role="img" aria-label="Downtime duration log chart">
        {cycles.map((cycle, index) => (
          <div key={cycle.id} className={`downtime-row ${cycle.status}`}>
            <div className="downtime-row-label">
              <strong>{cycle.status === "active" ? "Active" : `Downtime ${index + 1}`}</strong>
              <span>{formatTime(cycle.startedAt)}</span>
            </div>
            <div className="downtime-row-track">
              <div style={{ width: `${Math.max((cycle.durationSeconds / max) * 100, 8)}%` }} />
            </div>
            <strong className="downtime-row-value">{formatDuration(cycle.durationSeconds)}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function buildQualityRows(records: ReturnType<typeof useQualityStore.getState>["inspectionLog"]) {
  return records.slice(0, 24).map(item => [
    formatTime(new Date(item.timestamp)),
    "Garment inspection",
    `${item.specLabel}: ${item.garmentAnalysis.styleDetection.style}, size ${item.garmentAnalysis.sizeMeasurement.detectedSize}`,
    item.garmentAnalysis.colourDetections.map(colour => `${colour.name} ${Math.round(colour.percentage)}%`).join(", "),
    <StatusPill key={item.id} label={item.decision} tone={item.decision === "PASS" ? "ok" : item.decision === "REWORK" ? "warn" : "bad"} />,
    `Overall confidence ${Math.round(item.garmentAnalysis.overallConfidence * 100)}%`,
  ]);
}

function labelIoTEvent(type: string) {
  if (type === "rework_triggered") return "Operator marked this piece for rework.";
  if (type === "rework_resolved") return "Rework was completed and closed.";
  if (type === "downtime_triggered") return "Machine downtime started.";
  return "Machine downtime ended.";
}

function SummaryRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="summary-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
