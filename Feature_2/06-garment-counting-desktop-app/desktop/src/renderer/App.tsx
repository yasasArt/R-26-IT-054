import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  BackendStatus,
  DesktopAppInfo,
  DeviceConfiguration,
  Employee,
  ProductionSession,
  SystemReadiness,
} from "../shared/types";
import { Icon } from "./components/Icon";
import { InlineNotice } from "./components/OperatorUi";
import { Sidebar } from "./components/Sidebar";
import { TitleBar } from "./components/TitleBar";
import { api } from "./lib/api";
import { useBluetoothController } from "./lib/bluetooth-controller";
import { AnalyticsScreen } from "./screens/AnalyticsScreen";
import { DeviceSetupScreen } from "./screens/DeviceSetupScreen";
import { LiveDashboardScreen } from "./screens/LiveDashboardScreen";
import { NewSessionScreen } from "./screens/NewSessionScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { useDesktopStore } from "./store/desktop-store";

export function App() {
  const [appInfo, setAppInfo] = useState<DesktopAppInfo | null>(null);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>({
    state: "starting",
    message: "Preparing your workstation…",
  });
  const [readiness, setReadiness] = useState<SystemReadiness | null>(null);
  const [configuration, setConfiguration] = useState<DeviceConfiguration | null>(null);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [sessions, setSessions] = useState<ProductionSession[]>([]);
  const [activeSession, setActiveSession] = useState<ProductionSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const activeNavigation = useDesktopStore((state) => state.activeNavigation);
  const setActiveNavigation = useDesktopStore((state) => state.setActiveNavigation);
  const controller = useBluetoothController();

  const activeEmployees = useMemo(() => employees.filter((employee) => employee.active), [employees]);

  const refreshWorkstation = useCallback(async () => {
    try {
      const [nextReadiness, nextConfiguration, nextEmployees, nextSessions, nextActiveSession] =
        await Promise.all([
          api.readiness(),
          api.deviceConfiguration(),
          api.employees(true),
          api.sessions(),
          api.activeSession(),
        ]);

      setReadiness(nextReadiness);
      setConfiguration(nextConfiguration);
      setEmployees(nextEmployees);
      setSessions(nextSessions);
      setActiveSession(nextActiveSession);
      setError(null);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Workstation information could not be loaded.");
    }
  }, []);

  useEffect(() => {
    let stopped = false;
    let polling = false;

    const checkDesktop = async () => {
      if (stopped || polling) return;
      polling = true;

      try {
        if (!window.garmentDesktop) {
          throw new Error("The secure desktop bridge is unavailable. Start the project using npm start.");
        }

        const [nextAppInfo, nextBackendStatus] = await Promise.all([
          window.garmentDesktop.getAppInfo(),
          window.garmentDesktop.getBackendStatus(),
        ]);

        if (stopped) return;

        setAppInfo(nextAppInfo);
        setBackendStatus(nextBackendStatus);

        if (nextBackendStatus.state === "ready") {
          await refreshWorkstation();
          window.clearInterval(timer);
        }
      } catch (caughtError) {
        if (!stopped) {
          setError(caughtError instanceof Error ? caughtError.message : "The workstation could not be prepared.");
        }
      } finally {
        polling = false;
      }
    };

    const timer = window.setInterval(() => void checkDesktop(), 650);
    void checkDesktop();

    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [refreshWorkstation]);

  useEffect(() => {
    if (backendStatus.state !== "ready") return;

    const models = readiness?.vision_models;
    const loading = models?.detector.state === "LOADING" || models?.classifier.state === "LOADING";
    if (!loading) return;

    const timer = window.setInterval(() => void refreshWorkstation(), 1800);
    return () => window.clearInterval(timer);
  }, [backendStatus.state, readiness?.vision_models, refreshWorkstation]);

  useEffect(() => {
    if (backendStatus.state !== "ready" || !controller.deviceId) return;
    if (controller.phase !== "CONNECTED" && controller.phase !== "RECONNECTING" && controller.phase !== "DISCONNECTED") {
      return;
    }

    void refreshWorkstation();
  }, [backendStatus.state, controller.deviceId, controller.lastButtonAt, controller.phase, refreshWorkstation]);

  const handleSessionCreated = useCallback(
    (session: ProductionSession) => {
      setActiveSession(session);
      setSessions((current) => [session, ...current.filter((existing) => existing.id !== session.id)]);
      setActiveNavigation("dashboard");
    },
    [setActiveNavigation],
  );

  const handleSessionUpdated = useCallback((session: ProductionSession) => {
    setActiveSession((previous) => {
      if (
        previous &&
        previous.id === session.id &&
        previous.total_pieces === session.total_pieces &&
        previous.operator_mode === session.operator_mode &&
        previous.status === session.status &&
        previous.average_cycle_seconds === session.average_cycle_seconds
      ) {
        return previous;
      }

      return session;
    });
  }, []);

  const handleSessionCompleted = useCallback(
    (session: ProductionSession) => {
      setActiveSession(null);
      setSessions((current) => [session, ...current.filter((existing) => existing.id !== session.id)]);
      setActiveNavigation("analytics");
      void refreshWorkstation();
    },
    [refreshWorkstation, setActiveNavigation],
  );

  function renderScreen() {
    if (backendStatus.state !== "ready") {
      return (
        <div className="startup-state">
          <span className="startup-icon"><Icon name={backendStatus.state === "error" ? "warning" : "refresh"} className={backendStatus.state === "error" ? undefined : "spin"} size={29} /></span>
          <h1>{backendStatus.state === "error" ? "Workstation startup needs attention" : "Preparing your workstation"}</h1>
          <p>{backendStatus.message}</p>
          {backendStatus.state === "error" ? <p>Follow the backend setup instructions in the project README, then reopen the desktop application.</p> : null}
        </div>
      );
    }

    if (activeNavigation === "setup") {
      return (
        <DeviceSetupScreen
          configuration={configuration}
          readiness={readiness}
          activeSession={activeSession}
          onUpdated={refreshWorkstation}
          onContinue={() => setActiveNavigation(activeSession ? "dashboard" : "session")}
        />
      );
    }

    if (activeNavigation === "session") {
      return (
        <NewSessionScreen
          employees={activeEmployees}
          configuration={configuration}
          readiness={readiness}
          activeSession={activeSession}
          onSessionCreated={handleSessionCreated}
          onManageEmployees={() => setActiveNavigation("settings")}
          onOpenSetup={() => setActiveNavigation("setup")}
        />
      );
    }

    if (activeNavigation === "dashboard") {
      return (
        <LiveDashboardScreen
          session={activeSession}
          onSessionUpdated={handleSessionUpdated}
          onSessionCompleted={handleSessionCompleted}
          onCreateSession={() => setActiveNavigation("session")}
        />
      );
    }

    if (activeNavigation === "analytics") {
      return <AnalyticsScreen employees={employees} sessions={sessions} />;
    }

    return (
      <SettingsScreen
        employees={employees}
        sessions={sessions}
        configuration={configuration}
        readiness={readiness}
        activeSession={activeSession}
        onUpdated={refreshWorkstation}
      />
    );
  }

  return (
    <div className="desktop-shell">
      <Sidebar appInfo={appInfo} />
      <div className="desktop-workspace">
        <TitleBar appInfo={appInfo} />
        <main className="workspace-content workspace-content-phase-two">
          {error ? <InlineNotice tone="warning">{error}</InlineNotice> : null}
          {renderScreen()}
        </main>
      </div>
    </div>
  );
}
