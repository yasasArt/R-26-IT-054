// components/dashboard/sewing/IoTCard.tsx
"use client";
import { useSewingStore } from "@/store/sewingStore";
import { cn } from "@/lib/utils";

export function IoTCard() {
  const { iotStatus, reworkActive, downtimeActive } = useSewingStore();
  const isOk = iotStatus === "connected";

  const switches = [
    { label: "Rework",   active: reworkActive,  color: "#FACC15" },
    { label: "Downtime", active: downtimeActive, color: "#EF4444" },
  ];

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{
        background: "#1A2536",
        border: `1px solid ${isOk ? "#243044" : "rgba(239,68,68,0.3)"}`,
        borderRadius: 12,
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 shrink-0"
        style={{ height: 44, background: "#131B26", borderBottom: "1px solid #243044" }}
      >
        <span className="font-mono text-text-muted uppercase" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
          IoT Device
        </span>
        <div
          className={cn("rounded-full shrink-0", isOk && "animate-pulse-slow")}
          style={{
            width: 7, height: 7,
            background: isOk ? "#22C55E" : "#EF4444",
            boxShadow: isOk ? "0 0 6px #22C55E" : "0 0 6px #EF4444",
          }}
        />
      </div>

      {/* Body */}
      <div style={{ padding: "12px 16px", flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
        {/* Info row */}
        <div className="grid grid-cols-2 gap-2">
          {[
            { l: "IP",      v: "192.168.1.105" },
            { l: "Latency", v: isOk ? "4 ms" : "—" },
          ].map(({ l, v }) => (
            <div key={l} style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 7, padding: "8px 10px" }}>
              <div className="font-mono text-dim uppercase" style={{ fontSize: 7, letterSpacing: "0.09em", marginBottom: 3 }}>{l}</div>
              <div className="font-mono text-text-primary" style={{ fontSize: 11 }}>{v}</div>
            </div>
          ))}
        </div>

        {/* Switch states */}
        <div className="space-y-1.5">
          {switches.map(sw => (
            <div
              key={sw.label}
              className="flex items-center justify-between rounded-lg px-3 py-2 transition-all duration-200"
              style={{
                background: sw.active ? `${sw.color}0D` : "#0B1017",
                border: `1px solid ${sw.active ? `${sw.color}35` : "#243044"}`,
              }}
            >
              <span className="font-mono text-text-muted" style={{ fontSize: 10 }}>
                {sw.label} Btn
              </span>
              <div className="flex items-center gap-1.5">
                <div
                  className={cn("rounded-full", sw.active && "animate-pulse-slow")}
                  style={{
                    width: 5, height: 5,
                    background: sw.active ? sw.color : "#3A4A5C",
                    boxShadow: sw.active ? `0 0 5px ${sw.color}` : "none",
                  }}
                />
                <span
                  className="font-mono font-semibold"
                  style={{ fontSize: 9, color: sw.active ? sw.color : "#3A4A5C" }}
                >
                  {sw.active ? "ACTIVE" : "Idle"}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}