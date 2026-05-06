"use client";

import { RotateCcw, ScanLine, Shirt, TriangleAlert } from "lucide-react";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { MetricCard, PageHeader, Panel, StatusPill } from "@/components/industrial/Primitives";
import { generateDetectionEvent } from "@/lib/mock/sewing.mock";
import { generateGarmentAnalysis } from "@/lib/mock/quality.mock";
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
        <MetricCard label="Pieces" value={sewing.pieceCount} sub="Sewing store" tone="ok" />
        <MetricCard label="Inspections" value={quality.inspectionLog.length} sub="Quality store" tone="cyan" />
        <MetricCard label="Demo source" value="Mock" sub="No backend required" tone="warn" />
      </div>

      <div className="grid grid-2" style={{ marginTop: 16 }}>
        <Panel title="Sewing Demo Actions" eyebrow="Feature 2">
          <div className="panel-body grid">
            <button className="btn btn-primary" onClick={addPiece}><Shirt size={17} /> Add detected piece</button>
            <button className="btn" onClick={sewing.reworkActive ? sewing.endRework : sewing.startRework}><TriangleAlert size={17} /> {sewing.reworkActive ? "Resolve rework" : "Trigger rework"}</button>
            <button className="btn btn-danger" onClick={sewing.downtimeActive ? sewing.endDowntime : sewing.startDowntime}><TriangleAlert size={17} /> {sewing.downtimeActive ? "Resolve downtime" : "Trigger downtime"}</button>
            <button className="btn" onClick={sewing.resetSewingState}><RotateCcw size={17} /> Reset sewing state</button>
          </div>
        </Panel>

        <Panel title="Quality Demo Actions" eyebrow="Features 3 + 4">
          <div className="panel-body grid">
            <button className="btn btn-primary" onClick={addInspection}><ScanLine size={17} /> Run garment inspection</button>
            <button className="btn" onClick={() => quality.setCalibration({ status: "error" })}><TriangleAlert size={17} /> Simulate calibration error</button>
            <button className="btn btn-success" onClick={() => quality.setCalibration({ status: "calibrated", pixelPerCmRatio: 18.4, lastCalibratedAt: new Date() })}><ScanLine size={17} /> Restore calibration</button>
            <button className="btn" onClick={quality.resetQualityState}><RotateCcw size={17} /> Reset quality state</button>
          </div>
        </Panel>
      </div>
    </div>
  );
}
