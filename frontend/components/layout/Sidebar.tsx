"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BarChart3, Cpu, Gauge, LogOut, MonitorCog, SlidersHorizontal } from "lucide-react";
import { APP_NAME, APP_SUBTITLE, ROUTES } from "@/lib/constants";
import { useWorkstationStore } from "@/store/workstationStore";

const NAV = [
  { label: "Live Monitor", href: "dashboard", icon: Gauge },
  { label: "Logs & History", href: ROUTES.LOGS, icon: BarChart3 },
  { label: "Device Status", href: ROUTES.DEVICES, icon: Cpu },
  { label: "Demo Panel", href: ROUTES.DEMO, icon: SlidersHorizontal },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { config, endSession } = useWorkstationStore();
  const dashboardHref = config.mode === "quality" ? ROUTES.DASHBOARD_QUALITY : ROUTES.DASHBOARD_SEWING;

  function closeSession() {
    endSession();
    router.replace(ROUTES.LOGIN);
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand">
          <div className="brand-mark"><MonitorCog size={21} /></div>
          <div>
            <h1 className="brand-title">{APP_NAME}</h1>
            <div className="brand-subtitle">{APP_SUBTITLE}</div>
          </div>
        </div>
      </div>

      <nav className="nav" aria-label="Primary navigation">
        {NAV.map(item => {
          const Icon = item.icon;
          const href = item.href === "dashboard" ? dashboardHref : item.href;
          const active = href.includes("dashboard") ? pathname.startsWith("/dashboard") : pathname === href;
          return (
            <Link key={item.label} href={href} className={`nav-link ${active ? "active" : ""}`}>
              <Icon size={17} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="grid" style={{ gap: 10 }}>
          <div>
            <div className="meta-label">Station</div>
            <strong>{config.stationId}</strong>
          </div>
          <div>
            <div className="meta-label">Operator</div>
            <strong>{config.operatorName || "Unassigned"}</strong>
          </div>
          <div>
            <div className="meta-label">Mode</div>
            <strong>{config.mode === "quality" ? "Quality Checker" : "Sewing Operator"}</strong>
          </div>
          <button type="button" className="btn btn-danger" onClick={closeSession}>
            <LogOut size={16} />
            End Session
          </button>
        </div>
      </div>
    </aside>
  );
}
