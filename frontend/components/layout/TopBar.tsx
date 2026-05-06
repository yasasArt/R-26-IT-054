"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import { Camera, Clock, HardDrive, RadioTower } from "lucide-react";
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
        <div className="eyebrow">Local workstation</div>
        <strong>{mode === "quality" ? "Quality Checker Area" : "Sewing Operator Area"}</strong>
      </div>
      <div className="topbar-right">
        <StatusPill label={`Camera ${cameraStatus}`} tone={cameraStatus === "live" ? "ok" : "bad"} pulse={cameraStatus === "live"} />
        {mode === "sewing" && <StatusPill label={`IoT ${iotStatus}`} tone={iotStatus === "connected" ? "ok" : "bad"} pulse={iotStatus === "connected"} />}
        <span className="status-pill"><Clock size={13} /> {elapsed} session</span>
        <span className="status-pill"><RadioTower size={13} /> {config.serverUrl}</span>
        <span className="status-pill"><Camera size={13} /> {config.cameraId}</span>
        <span className="status-pill"><HardDrive size={13} /> {clock}</span>
        <ThemeToggle compact />
      </div>
    </header>
  );
}
