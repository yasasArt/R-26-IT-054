import type { DesktopAppInfo } from "../../shared/types";
import { useDesktopStore, type NavigationItem } from "../store/desktop-store";
import { BrandMark } from "./BrandMark";
import { Icon, type IconName } from "./Icon";

interface SidebarItem {
  label: string;
  icon: IconName;
  id: NavigationItem;
}

const monitorItems: SidebarItem[] = [
  { label: "Device setup", icon: "shield", id: "setup" },
  { label: "New session", icon: "plus", id: "session" },
  { label: "Live production", icon: "activity", id: "dashboard" },
];

const insightItems: SidebarItem[] = [
  { label: "Analytics", icon: "report", id: "analytics" },
  { label: "Settings", icon: "settings", id: "settings" },
];

function NavigationGroup({ title, items }: { title: string; items: SidebarItem[] }) {
  const activeNavigation = useDesktopStore((state) => state.activeNavigation);
  const setActiveNavigation = useDesktopStore((state) => state.setActiveNavigation);

  return (
    <section className="sidebar-group">
      <p className="sidebar-group-label">{title}</p>
      <div className="sidebar-links">
        {items.map((item) => (
          <button
            key={item.label}
            type="button"
            className={`sidebar-link ${item.id === activeNavigation ? "is-active" : ""}`}
            onClick={() => setActiveNavigation(item.id)}
          >
            <Icon name={item.icon} size={17} />
            <span>{item.label}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

export function Sidebar({ appInfo }: { appInfo: DesktopAppInfo | null }) {
  return (
    <aside className="sidebar">
      <div className="brand-block">
        <span className="brand-symbol"><BrandMark /></span>
        <div>
          <p className="brand-name">Garment Counter</p>
          <p className="brand-caption">Workstation intelligence</p>
        </div>
      </div>

      <div className="workspace-card">
        <span className="workspace-indicator" />
        <div>
          <p className="workspace-title">Local workstation</p>
          <p className="workspace-subtitle">Factory-floor operations</p>
        </div>
      </div>

      <nav className="sidebar-navigation" aria-label="Desktop navigation">
        <NavigationGroup title="MONITOR" items={monitorItems} />
        <NavigationGroup title="INSIGHTS" items={insightItems} />
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-security">
          <Icon name="lock" size={15} />
          <span>Offline-first architecture</span>
        </div>
        <p className="sidebar-version">Production release · v{appInfo?.appVersion || "1.0.3"}</p>
      </div>
    </aside>
  );
}
