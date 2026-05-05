"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  ScrollText,
  HardDrive,
  LogOut,
  Eye,
} from "lucide-react";
import { useWorkstationStore } from "@/store/workstationStore";
import { NavLink } from "./NavLink";
import { ModeIndicator } from "./ModeIndicator";
import { cn } from "@/lib/utils";
import { APP_NAME, ROUTES } from "@/lib/constants";

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

  return (
    <aside className="w-56 h-screen flex flex-col shrink-0" style={{ background: "#131B26", borderRight: "1px solid #243044" }}>

      {/* ── Brand ─────────────────────────────────────────── */}
      <Link
        href={dashHref}
        className="h-14 flex items-center gap-3 px-4 transition-colors hover:bg-card/40"
        style={{ borderBottom: "1px solid #243044" }}
      >
        <div
          className="flex items-center justify-center shrink-0"
          style={{
            width: 28, height: 28, borderRadius: 8,
            background: "rgba(59,130,246,0.12)",
            border: "1px solid rgba(59,130,246,0.28)",
            boxShadow: "0 0 10px rgba(59,130,246,0.12)",
          }}
        >
          <Eye size={13} className="text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <div
            className="font-display font-bold text-text-primary truncate leading-tight"
            style={{ fontSize: 12 }}
          >
            {APP_NAME}
          </div>
          <div
            className="font-mono text-text-muted uppercase mt-px"
            style={{ fontSize: 8, letterSpacing: "0.1em" }}
          >
            Workstation
          </div>
        </div>
      </Link>

      {/* ── Mode badge ─────────────────────────────────────── */}
      {mode && (
        <div className="px-3 py-2.5" style={{ borderBottom: "1px solid #243044" }}>
          <ModeIndicator mode={mode} size="xs" className="w-full justify-center" />
        </div>
      )}

      {/* ── Navigation ─────────────────────────────────────── */}
      <nav className="flex-1 px-2 pt-3 space-y-0.5 overflow-y-auto">
        <div
          className="font-mono text-dim uppercase px-3 pb-2"
          style={{ fontSize: 8, letterSpacing: "0.15em" }}
        >
          Navigation
        </div>
        <NavLink href={dashHref}       label="Live Monitor"   icon={Activity}   />
        <NavLink href={ROUTES.LOGS}    label="Logs & History" icon={ScrollText} />
        <NavLink href={ROUTES.DEVICES} label="Device Status"  icon={HardDrive}  />
      </nav>

      {/* ── Session footer ─────────────────────────────────── */}
      <div className="p-3 space-y-2.5" style={{ borderTop: "1px solid #243044" }}>

        {/* Station & operator rows */}
        <div className="space-y-1.5 px-1">
          {[
            { l: "Station",  v: config.stationId   },
            ...(config.operatorName ? [{ l: "Operator", v: config.operatorName }] : []),
          ].map(({ l, v }) => (
            <div key={l} className="flex items-center justify-between gap-2">
              <span
                className="font-mono text-dim uppercase shrink-0"
                style={{ fontSize: 8, letterSpacing: "0.1em" }}
              >
                {l}
              </span>
              <span
                className="font-mono text-text-primary truncate text-right"
                style={{ fontSize: 11, maxWidth: 108 }}
              >
                {v}
              </span>
            </div>
          ))}
        </div>

        {/* End session button */}
        <button
          type="button"
          onClick={handleEnd}
          className={cn(
            "w-full flex items-center gap-2.5 px-3 py-2 rounded-badge cursor-pointer",
            "font-display text-text-muted transition-all duration-150",
            "hover:text-danger hover:bg-danger/10",
            "border border-transparent hover:border-danger/20"
          )}
          style={{ fontSize: 12 }}
        >
          <LogOut size={13} />
          <span>End Session</span>
        </button>
      </div>
    </aside>
  );
}
