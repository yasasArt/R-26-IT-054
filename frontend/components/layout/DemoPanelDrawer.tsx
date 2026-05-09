// components/layout/DemoPanelDrawer.tsx
"use client";
import { useEffect } from "react";
import { Keyboard, ScanLine, Shirt, TimerReset, TriangleAlert, X, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { generateDetectionEvent } from "@/lib/mock/sewing.mock";
import { generateGarmentAnalysis } from "@/lib/mock/quality.mock";
import { useQualityStore } from "@/store/qualityStore";
import { useSewingStore } from "@/store/sewingStore";
import { useWorkstationStore } from "@/store/workstationStore";

interface DemoPanelDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export function DemoPanelDrawer({ isOpen, onClose }: DemoPanelDrawerProps) {
  const { config } = useWorkstationStore();
  const sewing = useSewingStore();
  const quality = useQualityStore();
  const isSewing = config.mode === "sewing";
  const reworkEvents = sewing.iotEvents.filter((event) => event.type.includes("rework"));
  const downtimeEvents = sewing.iotEvents.filter((event) => event.type.includes("downtime"));
  const latestSewingEvent = sewing.iotEvents[0] || sewing.detectionLog[0];

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

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
    window.setTimeout(() => quality.recordInspection(analysis), 600);
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          "fixed inset-0 bg-black/50 z-40 transition-opacity duration-300",
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={cn(
          "fixed top-0 right-0 h-full w-80 z-50",
          "bg-card border-l-2 border-orange",
          "transform transition-transform duration-300 ease-out",
          "flex flex-col",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Header */}
        <div className="h-12 border-b border-card-border px-4 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <Zap size={14} className="text-orange" />
            <span className="text-[11px] font-mono font-bold text-orange uppercase tracking-[3px]">
              Demo Panel
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary transition-colors cursor-pointer p-1 rounded hover:bg-card-border"
          >
            <X size={15} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          <div className="grid gap-2">
            <div className="panel" style={{ boxShadow: "none", padding: 10 }}>
              <div className="meta-label">Active demo mode</div>
              <strong>{isSewing ? "Sewing workstation" : "Quality inspection"}</strong>
            </div>

            <div className="panel" style={{ boxShadow: "none", padding: 10 }}>
              <div className="meta-label">Current records</div>
              <div className="grid" style={{ gap: 6, marginTop: 8 }}>
                {isSewing ? (
                  <>
                    <DemoFact label="Pieces" value={sewing.pieceCount} />
                    <DemoFact label="Rework actions" value={reworkEvents.length} />
                    <DemoFact label="Downtime actions" value={downtimeEvents.length} />
                    <DemoFact label="Machine" value={sewing.downtimeActive ? "Downtime" : sewing.reworkActive ? "Rework" : "Running"} />
                  </>
                ) : (
                  <>
                    <DemoFact label="Inspections" value={quality.inspectionLog.length} />
                    <DemoFact label="Pass rate" value={quality.inspectionLog.length ? `${Math.round((quality.approvedCount / quality.inspectionLog.length) * 100)}%` : "—"} />
                    <DemoFact label="Rework" value={quality.reworkCount} />
                    <DemoFact label="Mismatch" value={quality.mismatchCount} />
                  </>
                )}
              </div>
            </div>

            <div className="grid" style={{ gap: 7 }}>
              <button className="btn btn-primary" onClick={isSewing ? addPiece : addInspection}>
                {isSewing ? <Shirt size={16} /> : <ScanLine size={16} />}
                {isSewing ? "Add detected piece" : "Run inspection"}
              </button>
              {isSewing ? (
                <>
                  <button className="btn" onClick={sewing.reworkActive ? sewing.endRework : sewing.startRework}>
                    <TriangleAlert size={16} />
                    {sewing.reworkActive ? "Resolve rework" : "Trigger rework"}
                  </button>
                  <button className="btn btn-danger" onClick={sewing.downtimeActive ? sewing.endDowntime : sewing.startDowntime}>
                    <TriangleAlert size={16} />
                    {sewing.downtimeActive ? "Resolve downtime" : "Trigger downtime"}
                  </button>
                </>
              ) : (
                <>
                  <button className="btn" onClick={() => quality.setCalibration({ status: "error" })}>
                    <TriangleAlert size={16} />
                    Calibration error
                  </button>
                  <button className="btn btn-success" onClick={() => quality.setCalibration({ status: "calibrated", pixelPerCmRatio: 18.4, lastCalibratedAt: new Date() })}>
                    <ScanLine size={16} />
                    Restore calibration
                  </button>
                </>
              )}
            </div>

            {isSewing && (
              <div className="panel" style={{ boxShadow: "none", padding: 10 }}>
                <div className="meta-label">Action balance</div>
                <div className="demo-action-chart">
                  <DemoActionBar label="Rework" value={reworkEvents.length} total={reworkEvents.length + downtimeEvents.length} tone="warn" />
                  <DemoActionBar label="Downtime" value={downtimeEvents.length} total={reworkEvents.length + downtimeEvents.length} tone="bad" />
                </div>
                <div className="demo-latest-event">
                  <TimerReset size={13} />
                  <span>{latestSewingEvent ? "Latest sewing event recorded" : "No sewing demo events yet"}</span>
                </div>
              </div>
            )}
          </div>

          {/* Keyboard shortcut reminder */}
          <div className="mt-3 flex items-center gap-2 bg-surface border border-card-border rounded-badge px-3 py-2">
            <Keyboard size={11} className="text-text-muted" />
            <span className="text-[10px] font-mono text-text-muted">
              Toggle:{" "}
              <kbd className="text-text-primary bg-card-border rounded px-1 py-px">
                Ctrl
              </kbd>{" "}
              +{" "}
              <kbd className="text-text-primary bg-card-border rounded px-1 py-px">
                Shift
              </kbd>{" "}
              +{" "}
              <kbd className="text-text-primary bg-card-border rounded px-1 py-px">
                D
              </kbd>
            </span>
          </div>
        </div>
      </div>
    </>
  );
}

function DemoFact({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 12 }}>
      <span className="text-text-muted">{label}</span>
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
