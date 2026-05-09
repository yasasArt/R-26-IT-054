"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BarChart3, Cpu, Gauge, LogOut, MonitorCog, PanelLeftClose, PanelLeftOpen, SlidersHorizontal } from "lucide-react";
import { APP_NAME, APP_SUBTITLE, ROUTES } from "@/lib/constants";
import { useWorkstationStore } from "@/store/workstationStore";

const NAV = [
  { label: "Live Monitor", href: "dashboard", icon: Gauge },
  { label: "Logs & History", href: ROUTES.LOGS, icon: BarChart3 },
  { label: "Device Status", href: ROUTES.DEVICES, icon: Cpu },
  { label: "Demo Panel", href: ROUTES.DEMO, icon: SlidersHorizontal },
];

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
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
          <div className="brand-mark"><MonitorCog size={18} /></div>
          <div className="sidebar-copy">
            <h1 className="brand-title">{APP_NAME}</h1>
            <div className="brand-subtitle">{APP_SUBTITLE}</div>
          </div>
        </div>
        <button type="button" className="sidebar-toggle" onClick={onToggle} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
          {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
        </button>
      </div>

      <nav className="nav" aria-label="Primary navigation">
        {NAV.map(item => {
          const Icon = item.icon;
          const href = item.href === "dashboard" ? dashboardHref : item.href;
          const active = href.includes("dashboard") ? pathname.startsWith("/dashboard") : pathname === href;
          return (
            <Link key={item.label} href={href} className={`nav-link ${active ? "active" : ""}`}>
              <Icon size={15} />
              <span className="nav-label">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div style={{ display: "grid", gap: 10, marginBottom: 12 }}>
          <FooterFact label="Station" value={config.stationId} />
          <FooterFact label="Operator" value={config.operatorName || "Unassigned"} />
          <FooterFact label="Mode" value={config.mode === "quality" ? "Quality Checker" : "Sewing Operator"} />
        </div>
        <button type="button" className="btn btn-danger" style={{ width: "100%" }} onClick={closeSession}>
          <LogOut size={14} />
          <span className="nav-label">End Session</span>
        </button>
      </div>
    </aside>
  );
}

function FooterFact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="meta-label">{label}</div>
      <strong style={{ fontSize: 12 }}>{value}</strong>
    </div>
  );
}
