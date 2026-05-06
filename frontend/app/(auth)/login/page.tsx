"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import {
  Camera,
  CheckCircle2,
  LockKeyhole,
  MonitorCog,
  Server,
} from "lucide-react";
import {
  AVAILABLE_STATIONS,
  APP_NAME,
  APP_SUBTITLE,
  DEMO_PIN,
  DEMO_SERVER_URL,
  ROUTES,
} from "@/lib/constants";
import { useWorkstationStore } from "@/store/workstationStore";
import { StatusPill } from "@/components/industrial/Primitives";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

export default function LoginPage() {
  const router = useRouter();
  const { setConfig, resetWorkstation } = useWorkstationStore();

  const [station, setStation] = useState(AVAILABLE_STATIONS[0]);
  const [pin, setPin] = useState(["", "", "", ""]);
  const [clock, setClock] = useState("--:--:--");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const refs = useRef<Array<HTMLInputElement | null>>([]);

  useEffect(() => {
    resetWorkstation();
    refs.current[0]?.focus();

    const updateClock = () => {
      setClock(format(new Date(), "HH:mm:ss"));
    };

    updateClock();
    const id = window.setInterval(updateClock, 1000);

    return () => window.clearInterval(id);
  }, [resetWorkstation]);

  function submit(value = pin.join("")) {
    if (value !== DEMO_PIN) {
      setError("Invalid demo PIN. Use 1234.");
      setPin(["", "", "", ""]);
      refs.current[0]?.focus();
      return;
    }

    setLoading(true);
    setConfig({
      stationId: station.id,
      stationLabel: station.label,
      serverUrl: DEMO_SERVER_URL,
    });

    window.setTimeout(() => router.push(ROUTES.SETUP), 450);
  }

  function handleDigit(index: number, value: string) {
    if (!/^\d?$/.test(value)) return;

    setError("");
    const next = [...pin];
    next[index] = value;
    setPin(next);

    if (value && index < 3) refs.current[index + 1]?.focus();
    if (value && index === 3 && next.every(Boolean)) submit(next.join(""));
  }

  return (
    <main className="auth-page">
      <header className="auth-header">
        <div className="brand">
          <div className="brand-mark">
            <MonitorCog size={22} />
          </div>
          <div>
            <h1 className="brand-title">{APP_NAME}</h1>
            <div className="brand-subtitle">{APP_SUBTITLE}</div>
          </div>
        </div>

        <div className="topbar-right">
          <StatusPill label="Local server online" tone="ok" pulse />
          <span className="status-pill">
            <Server size={13} /> {DEMO_SERVER_URL}
          </span>
          <span className="status-pill">
            <Camera size={13} /> Camera bus ready
          </span>
          <span className="status-pill" suppressHydrationWarning>
            {clock}
          </span>
          <ThemeToggle compact />
        </div>
      </header>

      <section className="auth-main">
        <div className="center-card animate-in">
          <div style={{ textAlign: "center", marginBottom: 26 }}>
            <div className="eyebrow">Factory station access</div>
            <h2 className="page-title">Start a local monitoring session</h2>
            <p className="muted" style={{ lineHeight: 1.55 }}>
              Select the workstation on the garment floor and enter the operator
              PIN.
            </p>
          </div>

          <div className="panel">
            <div className="panel-header">
              <div>
                <div className="eyebrow">Station</div>
                <h3 className="panel-title">Access Control</h3>
              </div>
              <StatusPill label="Demo PIN 1234" tone="info" />
            </div>

            <div className="panel-body grid" style={{ gap: 20 }}>
              <label className="field">
                <span className="meta-label">Assigned workstation</span>
                <select
                  className="select"
                  value={station.id}
                  onChange={(event) => {
                    const next = AVAILABLE_STATIONS.find(
                      (item) => item.id === event.target.value
                    );
                    if (next) setStation(next);
                  }}
                >
                  {AVAILABLE_STATIONS.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span className="meta-label">4-digit operator PIN</span>
                <div className="pin-grid">
                  {pin.map((digit, index) => (
                    <input
                      key={index}
                      ref={(node) => {
                        refs.current[index] = node;
                      }}
                      className="input pin-box"
                      value={digit}
                      inputMode="numeric"
                      type="password"
                      maxLength={1}
                      onChange={(event) =>
                        handleDigit(index, event.target.value)
                      }
                      onKeyDown={(event) => {
                        if (
                          event.key === "Backspace" &&
                          !pin[index] &&
                          index > 0
                        ) {
                          refs.current[index - 1]?.focus();
                        }

                        if (event.key === "Enter" && pin.every(Boolean)) {
                          submit();
                        }
                      }}
                    />
                  ))}
                </div>
              </label>

              <div
                style={{
                  minHeight: 24,
                  color: error ? "var(--red)" : "var(--green)",
                  fontFamily: "var(--font-ibm-plex-mono)",
                  fontSize: 12,
                }}
              >
                {error ||
                  (loading
                    ? "Access granted. Loading setup..."
                    : "Local-only prototype. No cloud authentication is used.")}
              </div>

              <button
                className="btn btn-primary"
                disabled={loading || !pin.every(Boolean)}
                onClick={() => submit()}
              >
                {loading ? (
                  <CheckCircle2 size={17} />
                ) : (
                  <LockKeyhole size={17} />
                )}
                Continue to Configuration
              </button>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}