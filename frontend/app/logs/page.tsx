"use client";

import type { ReactNode } from "react";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { DataTable, MetricCard, PageHeader, Panel, StatusPill } from "@/components/industrial/Primitives";
import { formatDuration, formatTime } from "@/lib/utils";
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
        <MetricCard label={isQuality ? "Latest decision" : "Operator actions"} value={isQuality ? latestQuality?.decision || "—" : sewing.iotEvents.length} sub={isQuality ? "Garment records" : "Rework and downtime history"} tone="cyan" />
        <MetricCard label="Operator" value={config.operatorName || "—"} sub="Active session" tone="muted" />
      </div>
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
                <SummaryRow label="Operator actions" value={sewing.iotEvents.length} />
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
      <div style={{ marginTop: 16 }}>
        <Panel title={isQuality ? "Inspection History" : "Sewing History"} eyebrow="Most recent first with full details">
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
      item.type.includes("rework") ? "Rework action" : "Downtime action",
      labelIoTEvent(item.type),
      item.durationSeconds !== undefined ? formatDuration(item.durationSeconds) : "Started",
      <StatusPill key={item.id} label={item.type.includes("resolved") ? "Closed" : "Started"} tone={item.type.includes("resolved") ? "ok" : item.type.includes("rework") ? "warn" : "bad"} />,
      `Triggered by ${item.triggeredBy}`,
    ] as ReactNode[],
  }));

  return [...detectionRows, ...actionRows]
    .sort((a, b) => b.time.getTime() - a.time.getTime())
    .slice(0, 24)
    .map(item => item.row);
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
