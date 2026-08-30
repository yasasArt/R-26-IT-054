import type { DesktopAppInfo } from "../../shared/types";
import { useDesktopStore } from "../store/desktop-store";
import { Icon } from "./Icon";

function formatPlatform(platform: NodeJS.Platform | undefined): string {
  if (platform === "darwin") return "macOS";
  if (platform === "win32") return "Windows";
  if (platform === "linux") return "Linux";
  return "Desktop";
}

export function TitleBar({ appInfo }: { appInfo: DesktopAppInfo | null }) {
  const isMacOS = appInfo?.platform === "darwin";
  const activeNavigation = useDesktopStore((state) => state.activeNavigation);
  const sectionTitles = {
    setup: "Device setup",
    session: "New session",
    dashboard: "Live production",
    analytics: "Analytics",
    settings: "Settings",
  };

  return (
    <header className={`titlebar ${isMacOS ? "is-macos" : ""}`}>
      <div className="titlebar-route">
        <span>Workstation</span>
        <span className="titlebar-divider">/</span>
        <strong>{sectionTitles[activeNavigation]}</strong>
      </div>

      <div className="titlebar-actions no-drag">
        <span className="platform-badge">{formatPlatform(appInfo?.platform)}</span>
        <span className="environment-badge">LOCAL</span>

        {!isMacOS ? (
          <div className="window-controls" aria-label="Window controls">
            <button
              type="button"
              aria-label="Minimize window"
              onClick={() => window.garmentDesktop.minimizeWindow()}
            >
              <Icon name="minimize" size={15} />
            </button>
            <button
              type="button"
              aria-label="Maximize window"
              onClick={() => window.garmentDesktop.toggleMaximizeWindow()}
            >
              <Icon name="maximize" size={14} />
            </button>
            <button
              type="button"
              className="window-close"
              aria-label="Close window"
              onClick={() => window.garmentDesktop.closeWindow()}
            >
              <Icon name="close" size={15} />
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
