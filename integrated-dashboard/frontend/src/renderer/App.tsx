import { useEffect, useState } from "react";

import { SewingWorkspace } from "@garment-counter/SewingWorkspace";
import { ReworkWorkspace } from "@garment-rework/ReworkWorkspace";
import { StyleColourWorkspace } from "@garment-style-colour/StyleColourWorkspace";
import { SizeWorkspace } from "@garment-size/SizeWorkspace";
import type { DesktopAppInfo } from "../shared/types";
import { LandingScreen } from "./modules/platform/LandingScreen";
import type { WorkstationId } from "./modules/platform/module-registry";
import { WorkstationSelectionScreen } from "./modules/platform/WorkstationSelectionScreen";

type PlatformScreen = "landing" | "selection" | "workstation";

export function App() {
  const [screen, setScreen] = useState<PlatformScreen>("landing");
  const [appInfo, setAppInfo] = useState<DesktopAppInfo | null>(null);
  const [selectedWorkstation, setSelectedWorkstation] = useState<WorkstationId | null>(null);

  useEffect(() => {
    let mounted = true;

    window.garmentDesktop?.getAppInfo().then((info) => {
      if (mounted) setAppInfo(info);
    }).catch(() => {
      // The platform overview remains usable while the secure desktop bridge initializes.
    });

    return () => {
      mounted = false;
    };
  }, []);

  const openSelection = () => setScreen("selection");

  if (screen === "landing") {
    return <LandingScreen appInfo={appInfo} onContinue={openSelection} />;
  }

  if (screen === "selection" || !selectedWorkstation) {
    return (
      <WorkstationSelectionScreen
        appInfo={appInfo}
        selectedWorkstation={selectedWorkstation}
        onSelect={setSelectedWorkstation}
        onContinue={() => setScreen("workstation")}
        onBack={() => setScreen("landing")}
      />
    );
  }

  if (selectedWorkstation === "rework") {
    return <ReworkWorkspace appInfo={appInfo} onExit={openSelection} />;
  }

  if (selectedWorkstation === "style-colour") {
    return <StyleColourWorkspace appInfo={appInfo} onExit={openSelection} />;
  }

  if (selectedWorkstation === "size") {
    return <SizeWorkspace appInfo={appInfo} onExit={openSelection} />;
  }

  return <SewingWorkspace onExit={openSelection} />;
}
