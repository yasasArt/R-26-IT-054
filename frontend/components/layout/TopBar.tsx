"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import { Camera, Clock, RadioTower } from "lucide-react";
import { useQualityStore } from "@/store/qualityStore";
import { useSewingStore } from "@/store/sewingStore";
import { useWorkstationStore } from "@/store/workstationStore";
import { StatusPill } from "@/components/industrial/Primitives";
import { ThemeToggle } from "./ThemeToggle";

export function TopBar() {
  const { config, sessionStartTime } = useWorkstationStore();
  const sewing = useSewingStore();
  const quality = useQualityStore();
  const [clock, setClock] = useState("");
  const [elapsed, setElapsed] = useState("00:00");

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setClock(format(now, "HH:mm:ss"));
      if (sessionStartTime) {
        const seconds = Math.floor((now.getTime() - new Date(sessionStartTime).getTime()) / 1000);
        const h = Math.floor(seconds / 3600).toString().padStart(2, "0");
        const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, "0");
        setElapsed(`${h}:${m}`);
      }
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [sessionStartTime]);

  const mode = config.mode;
  const cameraStatus = mode === "quality" ? quality.cameraStatus : sewing.cameraStatus;
  const iotStatus = sewing.iotStatus;

  return (
    <header className="topbar">
      <div>
        <div className="eyebrow">Local workstation · {config.stationId}</div>
        <strong style={{ fontSize: 13 }}>{mode === "quality" ? "Quality Checker Area" : "Sewing Operator Area"}</strong>
      </div>

      <div className="topbar-right">
        {/* Live device status */}
        <StatusPill
          label={`Camera ${cameraStatus}`}
          tone={cameraStatus === "live" ? "ok" : "bad"}
          pulse={cameraStatus === "live"}
        />
        {mode === "sewing" && (
          <StatusPill
            label={`IoT ${iotStatus}`}
            tone={iotStatus === "connected" ? "ok" : "bad"}
            pulse={iotStatus === "connected"}
          />
        )}

        {/* Divider */}
        <span style={{ width: 1, height: 16, background: "var(--line)", flexShrink: 0 }} />

        {/* Session + connection info */}
        <span className="status-pill" title={`Server: ${config.serverUrl}`}>
          <RadioTower size={11} />
          {config.serverUrl}
        </span>
        <span className="status-pill">
          <Camera size={11} />
          {config.cameraId}
        </span>
        <span className="status-pill">
          <Clock size={11} />
          {elapsed}
        </span>

        {/* Divider */}
        <span style={{ width: 1, height: 16, background: "var(--line)", flexShrink: 0 }} />

        <span
          className="status-pill"
          suppressHydrationWarning
          style={{ fontVariantNumeric: "tabular-nums", minWidth: 72, justifyContent: "center" }}
        >
          {clock}
        </span>
        <ThemeToggle compact />
      </div>
    </header>
  );
}
