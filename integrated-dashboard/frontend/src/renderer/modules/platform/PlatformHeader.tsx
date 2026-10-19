import type { DesktopAppInfo } from "../../../shared/types";
import { BrandMark } from "@garment-counter/components/BrandMark";
import { Icon } from "@garment-counter/components/Icon";

export function PlatformHeader({
  appInfo,
  compact = false,
  onHome,
}: {
  appInfo: DesktopAppInfo | null;
  compact?: boolean;
  onHome?: () => void;
}) {
  const isMacOS = appInfo?.platform === "darwin";

  return (
    <header className={`platform-topbar ${isMacOS ? "is-macos" : ""} ${compact ? "is-compact" : ""}`}>
      <button
        type="button"
        className="platform-brand"
        onClick={onHome}
        disabled={!onHome}
        aria-label={onHome ? "Return to the platform overview" : "Garment Intelligence Platform"}
      >
        <span className="platform-brand-mark"><BrandMark /></span>
        <span className="platform-brand-copy">
          <strong>Garment Intelligence</strong>
          <span>Integrated manufacturing platform</span>
        </span>
      </button>

      <div className="platform-topbar-actions no-drag">
        <span className="platform-local-badge">
          <span />
          LOCAL PLATFORM
        </span>

        {!isMacOS ? (
          <div className="window-controls" aria-label="Window controls">
            <button type="button" aria-label="Minimize window" onClick={() => window.garmentDesktop?.minimizeWindow()}>
              <Icon name="minimize" size={15} />
            </button>
            <button type="button" aria-label="Maximize window" onClick={() => window.garmentDesktop?.toggleMaximizeWindow()}>
              <Icon name="maximize" size={14} />
            </button>
            <button
              type="button"
              className="window-close"
              aria-label="Close window"
              onClick={() => window.garmentDesktop?.closeWindow()}
            >
              <Icon name="close" size={15} />
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
