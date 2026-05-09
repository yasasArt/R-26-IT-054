"use client";

import { RotateCcw, ScanLine, Shirt, TimerReset, TriangleAlert } from "lucide-react";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { DataTable, MetricCard, PageHeader, Panel, StatusPill } from "@/components/industrial/Primitives";
import { generateDetectionEvent } from "@/lib/mock/sewing.mock";
import { generateGarmentAnalysis } from "@/lib/mock/quality.mock";
import { formatDuration, formatTime } from "@/lib/utils";
import { useQualityStore } from "@/store/qualityStore";
import { useSewingStore } from "@/store/sewingStore";
import { useWorkstationStore } from "@/store/workstationStore";

export default function DemoPage() {
  return (
    <DashboardShell>
      <DemoContent />
    </DashboardShell>
  );
}

function DemoContent() {
  const { config } = useWorkstationStore();
  const sewing = useSewingStore();
  const quality = useQualityStore();
  const isSewing = config.mode === "sewing";
  const reworkCount = sewing.totalReworkCount + (sewing.reworkActive ? 1 : 0);
  const downtimeCount = sewing.iotEvents.filter((item) => item.type === "downtime_resolved").length + (sewing.downtimeActive ? 1 : 0);
  const recentRows = isSewing
    ? [
        ...sewing.detectionLog.map(item => ({
          time: new Date(item.timestamp),
          row: [
          formatTime(new Date(item.timestamp)),
          `Piece #${item.pieceNumber}`,
          `${item.cycleTimeSeconds}s cycle`,
          <StatusPill key={item.id} label={`${Math.round(item.confidenceScore * 100)}% confidence`} tone="ok" />,
          ],
        })),
        ...sewing.iotEvents.map(item => ({
          time: new Date(item.timestamp),
          row: [
          formatTime(new Date(item.timestamp)),
          item.type.includes("rework") ? "Rework" : "Downtime",
          item.durationSeconds ? formatDuration(item.durationSeconds) : "Started",
          <StatusPill key={item.id} label={item.type.includes("resolved") ? "Resolved" : "Active"} tone={item.type.includes("resolved") ? "ok" : item.type.includes("rework") ? "warn" : "bad"} />,
          ],
        })),
      ].sort((a, b) => b.time.getTime() - a.time.getTime()).slice(0, 10).map((item) => item.row)
    : quality.inspectionLog.slice(0, 8).map(item => [
        formatTime(new Date(item.timestamp)),
        item.specLabel,
        `${item.garmentAnalysis.styleDetection.style} · ${item.garmentAnalysis.sizeMeasurement.detectedSize}`,
        <StatusPill key={item.id} label={item.decision} tone={item.decision === "PASS" ? "ok" : item.decision === "REWORK" ? "warn" : "bad"} />,
      ]);

  function addPiece() {
    const event = generateDetectionEvent(sewing.pieceCount + 1);
    sewing.incrementPiece({
      timestamp: event.timestamp,
      pieceNumber: event.pieceNumber,
      cycleTimeSeconds: event.cycleTimeSeconds,
      operatorStatus: event.operatorStatus,
      confidenceScore: event.confidenceScore,
      signalA: event.signalA,
      signalB: event.signalB,
    });
  }

  function addInspection() {
    const analysis = generateGarmentAnalysis();
    quality.setIsAnalysing(true);
    quality.setCurrentGarment(analysis);
    window.setTimeout(() => quality.recordInspection(analysis), 900);
  }

  return (
    <div className="animate-in">
      <PageHeader
        eyebrow="Demo control panel"
        title="Presentation controls"
        description="Manual controls for panel demonstrations. These actions mutate only local mock state and are designed for final-year project progress reviews."
        actions={<StatusPill label={isSewing ? "Sewing script" : "Quality script"} tone="info" />}
      />

      <div className="grid grid-4">
        <MetricCard label="Configured mode" value={isSewing ? "Sewing" : "Quality"} sub={config.stationId} tone="info" />
        <MetricCard label={isSewing ? "Pieces" : "Inspections"} value={isSewing ? sewing.pieceCount : quality.inspectionLog.length} sub={isSewing ? `${sewing.detectionLog.length} count records` : `${quality.approvedCount} pass, ${quality.reworkCount} rework`} tone="ok" />
        <MetricCard label={isSewing ? "Rework" : "Pass rate"} value={isSewing ? reworkCount : quality.inspectionLog.length ? `${Math.round((quality.approvedCount / quality.inspectionLog.length) * 100)}%` : "—"} sub={isSewing ? "Completed plus active cycles" : "Accepted inspections"} tone="cyan" />
        <MetricCard label="Active script" value={isSewing ? "Sewing" : "Quality"} sub="Buttons below follow selected mode" tone="warn" />
      </div>

      <div className="grid grid-3" style={{ marginTop: 16 }}>
        {isSewing ? (
          <Panel title="Active Sewing Controls" eyebrow="Feature 2">
            <div className="panel-body grid">
              <button className="btn btn-primary" onClick={addPiece}><Shirt size={17} /> Add detected piece</button>
              <button className="btn" onClick={sewing.reworkActive ? sewing.endRework : sewing.startRework}><TriangleAlert size={17} /> {sewing.reworkActive ? "Resolve rework" : "Trigger rework"}</button>
              <button className="btn btn-danger" onClick={sewing.downtimeActive ? sewing.endDowntime : sewing.startDowntime}><TriangleAlert size={17} /> {sewing.downtimeActive ? "Resolve downtime" : "Trigger downtime"}</button>
              <button className="btn" onClick={sewing.resetSewingState}><RotateCcw size={17} /> Reset sewing state</button>
            </div>
          </Panel>
        ) : (
          <Panel title="Active Quality Controls" eyebrow="Features 3 + 4">
            <div className="panel-body grid">
              <button className="btn btn-primary" onClick={addInspection}><ScanLine size={17} /> Run garment inspection</button>
              <button className="btn" onClick={() => quality.setCalibration({ status: "error" })}><TriangleAlert size={17} /> Simulate calibration error</button>
              <button className="btn btn-success" onClick={() => quality.setCalibration({ status: "calibrated", pixelPerCmRatio: 18.4, lastCalibratedAt: new Date() })}><ScanLine size={17} /> Restore calibration</button>
              <button className="btn" onClick={quality.resetQualityState}><RotateCcw size={17} /> Reset quality state</button>
            </div>
          </Panel>
        )}

        {isSewing && (
          <Panel title="Rework and Downtime Mix" eyebrow="Operator button events">
            <div className="panel-body demo-page-chart">
              <DemoActionBar label="Rework" value={reworkCount} total={reworkCount + downtimeCount} tone="warn" />
              <DemoActionBar label="Downtime" value={downtimeCount} total={reworkCount + downtimeCount} tone="bad" />
              <div className="demo-latest-event"><TimerReset size={14} /><span>Use trigger and resolve to create complete history rows.</span></div>
            </div>
          </Panel>
        )}

        <Panel title="Live Demo Data" eyebrow="What changed after button clicks">
          <div className="stat-list">
            {isSewing ? (
              <>
                <SummaryRow label="Last piece" value={sewing.detectionLog[0] ? `#${sewing.detectionLog[0].pieceNumber}` : "—"} />
                <SummaryRow label="Last cycle" value={sewing.detectionLog[0] ? `${sewing.detectionLog[0].cycleTimeSeconds}s` : "—"} />
                <SummaryRow label="Rework cycles" value={reworkCount} />
                <SummaryRow label="Downtime cycles" value={downtimeCount} />
                <SummaryRow label="Machine status" value={sewing.downtimeActive ? "Downtime" : sewing.reworkActive ? "Rework" : "Running"} />
              </>
            ) : (
              <>
                <SummaryRow label="Last spec" value={quality.inspectionLog[0]?.specLabel || "—"} />
                <SummaryRow label="Last decision" value={quality.inspectionLog[0]?.decision || "—"} />
                <SummaryRow label="Calibration" value={quality.calibration.status} />
              </>
            )}
          </div>
        </Panel>
      </div>

      <div style={{ marginTop: 16 }}>
        <Panel title="Recent Demo Output" eyebrow={isSewing ? "Sewing events created by controls" : "Quality events created by controls"}>
          <DataTable headers={["Time", "Record", "Details", "Status"]} rows={recentRows} emptyMessage="No demo records yet. Press an action button above to create data." />
        </Panel>
      </div>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="summary-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DemoActionBar({ label, value, total, tone }: { label: string; value: number; total: number; tone: "warn" | "bad" }) {
  const width = total ? Math.max((value / total) * 100, value ? 12 : 0) : 0;
  return (
    <div className="demo-action-row">
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <div className="demo-action-track">
        <div className={tone} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}
