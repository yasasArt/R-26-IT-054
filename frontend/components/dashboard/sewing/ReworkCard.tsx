// components/dashboard/sewing/ReworkCard.tsx
"use client";

import { useEffect, useState } from "react";
import { useSewingStore } from "@/store/sewingStore";
import { formatDuration, formatTime } from "@/lib/utils";

export function ReworkCard() {
  const {
    reworkActive,
    reworkStartTime,
    totalReworkCount,
    iotEvents,
  } = useSewingStore();

  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!reworkActive || !reworkStartTime) {
      return;
    }

    const startTime = new Date(reworkStartTime).getTime();

    const id = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => window.clearInterval(id);
  }, [reworkActive, reworkStartTime]);

  const displayedElapsed = reworkActive ? elapsed : 0;
  const lastRework = iotEvents.find((e) => e.type === "rework_triggered");

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{
        background: "#1A2536",
        border: `1px solid ${reworkActive ? "rgba(250,204,21,0.4)" : "#243044"}`,
        borderRadius: 12,
        boxShadow: reworkActive ? "0 0 18px rgba(250,204,21,0.1)" : "none",
        transition: "border-color 0.3s, box-shadow 0.3s",
      }}
    >
      {/* Header */}
      <div
        className="flex shrink-0 items-center justify-between px-4"
        style={{
          height: 44,
          background: "#131B26",
          borderBottom: `1px solid ${reworkActive ? "rgba(250,204,21,0.2)" : "#243044"}`,
        }}
      >
        <span
          className="font-mono text-text-muted uppercase"
          style={{ fontSize: 9, letterSpacing: "0.14em" }}
        >
          Rework
        </span>

        <div
          className={reworkActive ? "animate-pulse-slow rounded-full" : "rounded-full"}
          style={{
            width: 7,
            height: 7,
            background: reworkActive ? "#FACC15" : "#3A4A5C",
            boxShadow: reworkActive ? "0 0 6px #FACC15" : "none",
          }}
        />
      </div>

      {/* Body */}
      <div
        style={{
          padding: "12px 16px",
          flex: 1,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {/* State */}
        <div
          className="flex items-center justify-between rounded-lg transition-all duration-300"
          style={{
            padding: "9px 12px",
            background: reworkActive
              ? "rgba(250,204,21,0.08)"
              : "rgba(255,255,255,0.02)",
            border: `1px solid ${reworkActive ? "rgba(250,204,21,0.25)" : "#243044"}`,
          }}
        >
          <div
            className="font-mono font-bold"
            style={{
              fontSize: 13,
              color: reworkActive ? "#FACC15" : "#3A4A5C",
            }}
          >
            {reworkActive ? "ACTIVE" : "Normal"}
          </div>

          {reworkActive && (
            <div className="font-mono font-bold text-warning" style={{ fontSize: 13 }}>
              {formatDuration(displayedElapsed)}
            </div>
          )}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-2">
          <div
            style={{
              background: "#0B1017",
              border: "1px solid #243044",
              borderRadius: 7,
              padding: "8px 10px",
            }}
          >
            <div
              className="font-mono text-dim uppercase"
              style={{
                fontSize: 7,
                letterSpacing: "0.09em",
                marginBottom: 4,
              }}
            >
              Total Today
            </div>
            <div className="font-mono font-bold text-warning" style={{ fontSize: 18, lineHeight: 1 }}>
              {totalReworkCount}
            </div>
          </div>

          <div
            style={{
              background: "#0B1017",
              border: "1px solid #243044",
              borderRadius: 7,
              padding: "8px 10px",
            }}
          >
            <div
              className="font-mono text-dim uppercase"
              style={{
                fontSize: 7,
                letterSpacing: "0.09em",
                marginBottom: 4,
              }}
            >
              Last Event
            </div>
            <div className="font-mono text-text-primary" style={{ fontSize: 10 }}>
              {lastRework ? formatTime(new Date(lastRework.timestamp)) : "None"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}