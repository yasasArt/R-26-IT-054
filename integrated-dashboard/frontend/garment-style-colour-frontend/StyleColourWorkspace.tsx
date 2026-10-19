import { useCallback, useEffect, useState } from "react";

import type { BackendStatus, DesktopAppInfo } from "@platform/shared/types";
import { FeatureStartupScreen } from "@platform/renderer/modules/platform/FeatureStartupScreen";
import ThreadScanApp from "./App";
import "./index.css";

/**
 * The packing area mounts the supplied ThreadScan project inside the common
 * platform shell. Its Python API, SQLite database, YOLO checkpoint and camera
 * pipeline stay isolated from the sewing and quality services.
 */
export function StyleColourWorkspace({
  appInfo,
  onExit,
}: {
  appInfo: DesktopAppInfo | null;
  onExit: () => void;
}) {
  const [status, setStatus] = useState<BackendStatus>({
    state: "starting",
    message: "Preparing the style and colour detection services…",
  });

  const startServices = useCallback(() => {
    let mounted = true;
    let timer: number | undefined;
    setStatus({ state: "starting", message: "Starting the data API, vision service, and garment-style model…" });

    const refresh = async () => {
      try {
        const nextStatus = await window.garmentDesktop.getStyleBackendStatus();
        if (!mounted) return;
        setStatus(nextStatus);
        if (nextStatus.state !== "ready") {
          timer = window.setTimeout(() => void refresh(), 800);
        }
      } catch (error) {
        if (!mounted) return;
        setStatus({
          state: "error",
          message: error instanceof Error ? error.message : "The packing services could not be prepared.",
        });
      }
    };

    window.garmentDesktop.startStyleServices()
      .then((nextStatus) => {
        if (!mounted) return;
        setStatus(nextStatus);
        if (nextStatus.state !== "ready") timer = window.setTimeout(() => void refresh(), 800);
      })
      .catch((error: unknown) => {
        if (!mounted) return;
        setStatus({
          state: "error",
          message: error instanceof Error ? error.message : "The packing services could not be started.",
        });
      });

    return () => {
      mounted = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    return startServices();
  }, [startServices]);

  const exitPacking = async () => {
    await window.garmentDesktop.stopStyleCamera().catch(() => {
      // The process may still be starting or already stopped; navigation can continue safely.
    });
    onExit();
  };

  if (status.state !== "ready") {
    return (
      <FeatureStartupScreen
        area="PACKING AREA"
        title="Garment Style and Colour Detection"
        message={status.message}
        state={status.state}
        runtimeLabel={appInfo?.packaged ? "Bundled feature services" : "Shared Python environment"}
        onBack={onExit}
        onRetry={() => { startServices(); }}
      />
    );
  }

  return <ThreadScanApp onExit={() => void exitPacking()} />;
}
