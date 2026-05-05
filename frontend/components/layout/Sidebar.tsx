// components/layout/Sidebar.tsx
"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Activity, ScrollText, HardDrive, LogOut, Eye } from "lucide-react";
import { useWorkstationStore } from "@/store/workstationStore";
import { NavLink } from "./NavLink";
import { cn } from "@/lib/utils";
import { APP_NAME, ROUTES } from "@/lib/constants";

const NAV_ITEMS = [
  { label: "Live Monitor",   icon: Activity,   key: "dashboard" },
  { label: "Logs & History", icon: ScrollText, key: ROUTES.LOGS },
  { label: "Device Status",  icon: HardDrive,  key: ROUTES.DEVICES },
] as const;

export function Sidebar() {
  const { config, endSession } = useWorkstationStore();
  const router = useRouter();
  const mode = config.mode;

  const dashHref =
    mode === "quality" ? ROUTES.DASHBOARD_QUALITY : ROUTES.DASHBOARD_SEWING;

  function handleEnd() {
    endSession();
    router.replace(ROUTES.LOGIN);
  }

  const modeColor  = mode === "sewing" ? "#22C55E" : "#3B82F6";
  const modeBg     = mode === "sewing" ? "rgba(34,197,94,0.1)"   : "rgba(59,130,246,0.1)";
  const modeBorder = mode === "sewing" ? "rgba(34,197,94,0.22)"  : "rgba(59,130,246,0.22)";
  const modeLabel  = mode === "sewing" ? "Sewing Area" : "Quality Area";

  return (
    <aside
      className="flex flex-col shrink-0"
      style={{
        width: 224,
        height: "100vh",
        background: "#131B26",
        borderRight: "1px solid #243044",
      }}
    >
      {/* ── Brand ─────────────────────────────────────── */}
      <Link
        href={dashHref}
        className="flex items-center gap-3 shrink-0 transition-colors hover:bg-white/4"
        style={{ height: 64, padding: "0 20px", borderBottom: "1px solid #243044" }}
      >
        <div
          className="flex items-center justify-center shrink-0"
          style={{
            width: 34, height: 34, borderRadius: 10,
            background: "rgba(59,130,246,0.12)",
            border: "1px solid rgba(59,130,246,0.3)",
          }}
        >
          <Eye size={16} className="text-accent" />
        </div>
        <div className="min-w-0">
          <div className="font-display font-bold text-text-primary truncate" style={{ fontSize: 13 }}>
            {APP_NAME}
          </div>
          <div className="font-mono text-text-muted" style={{ fontSize: 8.5, letterSpacing: "0.12em", marginTop: 2 }}>
            WORKSTATION
          </div>
        </div>
      </Link>

      {/* ── Mode badge ─────────────────────────────────── */}
      {mode && (
        <div
          className="flex items-center shrink-0 px-4"
          style={{ height: 46, borderBottom: "1px solid #243044" }}
        >
          <div
            className="flex items-center gap-2 w-full px-3 py-1.5 rounded-lg"
            style={{ background: modeBg, border: `1px solid ${modeBorder}` }}
          >
            <div
              className="rounded-full shrink-0 animate-pulse-slow"
              style={{ width: 6, height: 6, background: modeColor, boxShadow: `0 0 6px ${modeColor}` }}
            />
            <span
              className="font-mono font-bold uppercase truncate"
              style={{ fontSize: 9, letterSpacing: "0.1em", color: modeColor }}
            >
              {modeLabel}
            </span>
          </div>
        </div>
      )}

      {/* ── Navigation ─────────────────────────────────── */}
      <nav className="flex-1 overflow-y-auto" style={{ padding: "12px 8px" }}>
        <div
          className="font-mono text-dim uppercase"
          style={{ fontSize: 8, letterSpacing: "0.18em", padding: "0 8px 10px" }}
        >
          Navigation
        </div>

        <div className="space-y-0.5">
          {NAV_ITEMS.map(({ label, icon, key }) => {
            const href = key === "dashboard" ? dashHref : key;
            return (
              <NavLink key={label} href={href} label={label} icon={icon} />
            );
          })}
        </div>
      </nav>

      {/* ── Footer ─────────────────────────────────────── */}
      <div
        className="shrink-0"
        style={{ borderTop: "1px solid #243044", padding: "14px 16px" }}
      >
        {/* Station / Operator */}
        <div className="space-y-2 mb-3">
          {[
            { label: "Station",  value: config.stationId },
            { label: "Operator", value: config.operatorName },
          ]
            .filter(r => r.value)
            .map(({ label, value }) => (
              <div key={label} className="flex items-center justify-between gap-2">
                <span
                  className="font-mono text-dim uppercase shrink-0"
                  style={{ fontSize: 8, letterSpacing: "0.1em" }}
                >
                  {label}
                </span>
                <span
                  className="font-mono text-text-primary text-right truncate"
                  style={{ fontSize: 11, maxWidth: 112 }}
                >
                  {value}
                </span>
              </div>
            ))}
        </div>

        {/* End session */}
        <button
          type="button"
          onClick={handleEnd}
          className={cn(
            "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg font-display cursor-pointer",
            "text-text-muted transition-all duration-150",
            "hover:text-danger hover:bg-danger/10",
            "border border-transparent hover:border-danger/20"
          )}
          style={{ fontSize: 12, background: "none" }}
        >
          <LogOut size={13} />
          <span>End Session</span>
        </button>
      </div>
    </aside>
  );
}