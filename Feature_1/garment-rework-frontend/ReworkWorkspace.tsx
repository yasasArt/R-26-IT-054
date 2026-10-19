import { useCallback, useEffect, useState } from "react";

import type { BackendStatus, DesktopAppInfo } from "@platform/shared/types";
import { FeatureStartupScreen } from "@platform/renderer/modules/platform/FeatureStartupScreen";
import ReworkApp from "./ReworkApp";
import "./index.css";

/** Starts the independently owned Rework Counter service before mounting its UI. */
export function ReworkWorkspace({
  appInfo,
  onExit,
}: {
  appInfo: DesktopAppInfo | null;
  onExit: () => void;
}) {
  const [status, setStatus] = useState<BackendStatus>({
    state: "starting",
    message: "Preparing the Rework Counter service…",
  });

  const startService = useCallback(() => {
    let mounted = true;
    setStatus({ state: "starting", message: "Starting the isolated Rework Counter service and loading its model…" });
    window.garmentDesktop.startReworkService()
      .then((nextStatus) => { if (mounted) setStatus(nextStatus); })
      .catch((error: unknown) => {
        if (mounted) setStatus({ state: "error", message: error instanceof Error ? error.message : "Rework Counter could not start." });
      });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    return startService();
  }, [startService]);

  const exit = async () => {
    await window.garmentDesktop.stopReworkCamera().catch(() => undefined);
    onExit();
  };

  if (status.state !== "ready") {
    return (
      <FeatureStartupScreen
        area="QUALITY CHECKING AREA"
        title="Rework Counter"
        message={status.message}
        state={status.state}
        runtimeLabel={appInfo?.packaged ? "Bundled feature service" : "Shared Python environment"}
        onBack={onExit}
        onRetry={() => { startService(); }}
      />
    );
  }

  return <ReworkApp onExit={() => void exit()} />;
}
