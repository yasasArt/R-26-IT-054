"use client";

import type { ReactElement } from "react";
import { Camera, Cpu, Network, Ruler } from "lucide-react";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { MetricCard, PageHeader, Panel, StatusPill } from "@/components/industrial/Primitives";
import { useQualityStore } from "@/store/qualityStore";
import { useSewingStore } from "@/store/sewingStore";
import { useWorkstationStore } from "@/store/workstationStore";

export default function DevicesPage() {
  return (
    <DashboardShell>
      <DevicesContent />
    </DashboardShell>
  );
}

function DevicesContent() {
  const { config } = useWorkstationStore();
  const sewing = useSewingStore();
  const quality = useQualityStore();
  const isSewing = config.mode === "sewing";

  return (
    <div className="animate-in">
      <PageHeader
        eyebrow="Device status"
        title="Local workstation hardware"
        description="Status of the single active camera channel and mode-specific peripherals. Sewing mode expects IoT; quality mode expects calibration data."
        actions={<StatusPill label="Local network only" tone="cyan" />}
      />

      <div className="grid grid-4">
        <MetricCard label="Camera" value={isSewing ? sewing.cameraStatus : quality.cameraStatus} sub={config.cameraLabel} tone="ok" />
        <MetricCard label="Server" value="Online" sub={config.serverUrl} tone="ok" />
        <MetricCard label="Mode" value={isSewing ? "Sewing" : "Quality"} sub="Configured workstation" tone="info" />
        <MetricCard label={isSewing ? "IoT" : "Calibration"} value={isSewing ? sewing.iotStatus : quality.calibration.status} sub={isSewing ? "ESP32 device" : `${quality.calibration.pixelPerCmRatio} px/cm`} tone="cyan" />
      </div>

      <div className="grid grid-2" style={{ marginTop: 16 }}>
        <Panel title="Camera Channel" eyebrow="Active visual input" action={<StatusPill label="Live" tone="ok" pulse />}>
          <div className="panel-body grid grid-2">
            <DeviceTile icon={<Camera />} label="Device label" value={config.cameraLabel} />
            <DeviceTile icon={<Network />} label="Camera ID" value={config.cameraId} />
            <DeviceTile icon={<Camera />} label="Resolution" value="1920 x 1080" />
            <DeviceTile icon={<Camera />} label="Frame rate" value="30 fps" />
          </div>
        </Panel>

        {isSewing ? (
          <Panel title="IoT Control Device" eyebrow="Sewing operator area" action={<StatusPill label={sewing.iotStatus} tone={sewing.iotStatus === "connected" ? "ok" : "bad"} />}>
            <div className="panel-body grid grid-2">
              <DeviceTile icon={<Cpu />} label="Model" value="ESP32-WROOM" />
              <DeviceTile icon={<Network />} label="IP address" value="192.168.1.105" />
              <DeviceTile icon={<Cpu />} label="Rework switch" value={sewing.reworkActive ? "Pressed" : "Ready"} />
              <DeviceTile icon={<Cpu />} label="Downtime switch" value={sewing.downtimeActive ? "Pressed" : "Ready"} />
            </div>
          </Panel>
        ) : (
          <Panel title="Calibration" eyebrow="Quality checker area" action={<StatusPill label={quality.calibration.status} tone={quality.calibration.status === "calibrated" ? "ok" : "bad"} />}>
            <div className="panel-body grid grid-2">
              <DeviceTile icon={<Ruler />} label="Reference object" value={`${quality.calibration.referenceObjectSizeCm} cm`} />
              <DeviceTile icon={<Ruler />} label="Pixel ratio" value={`${quality.calibration.pixelPerCmRatio} px/cm`} />
              <DeviceTile icon={<Camera />} label="Camera" value={quality.calibration.cameraId} />
              <DeviceTile icon={<Ruler />} label="Last calibrated" value={quality.calibration.lastCalibratedAt ? "Current session" : "Unknown"} />
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}

function DeviceTile({ icon, label, value }: { icon: ReactElement; label: string; value: string | number }) {
  return (
    <div className="panel" style={{ boxShadow: "none", padding: 16 }}>
      <div className="cyan">{icon}</div>
      <div className="meta-label" style={{ marginTop: 10 }}>{label}</div>
      <strong>{value}</strong>
    </div>
  );
}
