import { useCallback, useEffect, useState } from "react";

import type { BackendStatus, DesktopAppInfo } from "@platform/shared/types";
import { FeatureStartupScreen } from "@platform/renderer/modules/platform/FeatureStartupScreen";
import SizeApp from "./SizeApp";
import "./globals.css";

export function SizeWorkspace({
  appInfo,
  onExit,
}: {
  appInfo: DesktopAppInfo | null;
  onExit: () => void;
}) {
  const [status, setStatus] = useState<BackendStatus>({
    state: "starting",
    message: "Loading the Garment Size Detection model…",
  });

  const startService = useCallback(() => {
    let mounted = true;
    setStatus({ state: "starting", message: "Loading the isolated Garment Size Detection service and trained model…" });
    window.garmentDesktop.startSizeService()
      .then((nextStatus) => { if (mounted) setStatus(nextStatus); })
      .catch((error: unknown) => {
        if (mounted) setStatus({ state: "error", message: error instanceof Error ? error.message : "Garment Size Detection could not start." });
      });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    return startService();
  }, [startService]);

  if (status.state !== "ready") {
    return (
      <FeatureStartupScreen
        area="PACKING AREA"
        title="Garment Size Detection"
        message={status.message}
        state={status.state}
        runtimeLabel={appInfo?.packaged ? "Bundled feature service" : "Shared Python environment"}
        onBack={onExit}
        onRetry={() => { startService(); }}
      />
    );
  }

  return <SizeApp onExit={onExit} />;
}
