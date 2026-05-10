"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Camera, Cpu, MonitorCog, Ruler, Shirt, UserRound } from "lucide-react";
import { APP_NAME, APP_SUBTITLE, PRODUCTION_SPECS, ROUTES } from "@/lib/constants";
import type { AreaMode } from "@/lib/types";
import { useQualityStore } from "@/store/qualityStore";
import { useWorkstationStore } from "@/store/workstationStore";
import { Panel, StatusPill } from "@/components/industrial/Primitives";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

type Step = 1 | 2 | 3;

export default function SetupPage() {
  const router = useRouter();
  const { config, setConfig, startSession } = useWorkstationStore();
  const { setActiveSpec } = useQualityStore();
  const [step, setStep] = useState<Step>(1);
  const [mode, setMode] = useState<AreaMode | null>(null);
  const [operator, setOperator] = useState("");
  const [target, setTarget] = useState(config.shiftTarget || 150);
  const [specId, setSpecId] = useState(PRODUCTION_SPECS[0].specId);
  const [error, setError] = useState("");

  const selectedSpec = PRODUCTION_SPECS.find(spec => spec.specId === specId) || PRODUCTION_SPECS[0];

  function next() {
    setError("");
    if (step === 1 && !mode) {
      setError("Select an area mode before continuing.");
      return;
    }
    if (step < 3) {
      setStep((step + 1) as Step);
      return;
    }
    if (!operator.trim() || !mode) {
      setError("Operator name is required to start the session.");
      return;
    }
    setConfig({ shiftTarget: target });
    setActiveSpec(selectedSpec);
    startSession(operator.trim(), mode);
    router.push(mode === "quality" ? ROUTES.DASHBOARD_QUALITY : ROUTES.DASHBOARD_SEWING);
  }

  function back() {
    if (step === 1) router.push(ROUTES.LOGIN);
    else setStep((step - 1) as Step);
  }

  return (
    <main className="setup-page">
      <header className="setup-header">
        <div className="brand">
          <div className="brand-mark"><MonitorCog size={22} /></div>
          <div>
            <h1 className="brand-title">{APP_NAME}</h1>
            <div className="brand-subtitle">{APP_SUBTITLE}</div>
          </div>
        </div>
        <div className="topbar-right">
          {[1, 2, 3].map(n => (
            <span key={n} className={`status-pill ${step === n ? "info" : n < step ? "ok" : ""}`}>Step {n}</span>
          ))}
          <ThemeToggle compact />
        </div>
      </header>

      <section className="setup-main animate-in">
        <div className="page-head">
          <div>
            <div className="eyebrow">Configuration wizard · Step {step} of 3</div>
            <h1 className="page-title">
              {step === 1 ? "Select workstation area mode" : step === 2 ? "Confirm local devices" : "Start production session"}
            </h1>
            <p className="muted" style={{ maxWidth: 680, lineHeight: 1.5, fontSize: 12.5, marginTop: 5 }}>
              This prototype is a single configurable local station. The selected mode controls the dashboard, device expectations, and simulated data stream.
            </p>
          </div>
          {error && <StatusPill label={error} tone="bad" />}
        </div>

        {step === 1 && (
          <div className="grid grid-2">
            <button className={`panel mode-card ${mode === "sewing" ? "selected" : ""}`} onClick={() => setMode("sewing")}>
              <div className="mode-visual">
                <div className="camera-overlay" />
                <div style={{ position: "absolute", left: 24, top: 28 }}><StatusPill label="Camera + IoT" tone="ok" /></div>
                <Shirt size={72} style={{ position: "absolute", left: "calc(50% - 36px)", top: 58, color: "var(--cyan)" }} />
                <Cpu size={28} style={{ position: "absolute", right: 28, bottom: 24, color: "var(--green)" }} />
              </div>
              <div className="panel-body">
                <h2 className="panel-title">Sewing Operator Area</h2>
                <p className="muted">Feature 2: piece counting, cycle-time analysis, rework and downtime actions through IoT.</p>
                <div className="segmented">
                  <StatusPill label="Output zone camera" tone="cyan" />
                  <StatusPill label="ESP32 required" tone="ok" />
                  <StatusPill label="Cycle timing" tone="info" />
                </div>
              </div>
            </button>

            <button className={`panel mode-card ${mode === "quality" ? "selected" : ""}`} onClick={() => setMode("quality")}>
              <div className="mode-visual">
                <div className="camera-overlay" />
                <div style={{ position: "absolute", left: 24, top: 28 }}><StatusPill label="Camera only" tone="info" /></div>
                <Ruler size={70} style={{ position: "absolute", left: "calc(50% - 35px)", top: 58, color: "var(--accent)" }} />
                <Camera size={28} style={{ position: "absolute", right: 28, bottom: 24, color: "var(--cyan)" }} />
              </div>
              <div className="panel-body">
                <h2 className="panel-title">Quality Checker Area</h2>
                <p className="muted">Features 3 + 4: colour recognition, style recognition, and size measurement using one fixed camera.</p>
                <div className="segmented">
                  <StatusPill label="No IoT" tone="warn" />
                  <StatusPill label="Spec matching" tone="info" />
                  <StatusPill label="Calibration" tone="cyan" />
                </div>
              </div>
            </button>
          </div>
        )}

        {step === 2 && mode && (
          <div className="grid grid-2">
            <Panel title="Camera Channel" eyebrow="Primary device" action={<StatusPill label="Live" tone="ok" pulse />}>
              <div className="panel-body grid">
                <div className="camera-frame" style={{ minHeight: 210 }}>
                  <div className="camera-overlay" />
                  <div className="scan-line" />
                  <div className="camera-caption">
                    <StatusPill label={mode === "sewing" ? "Output zone selected" : "Inspection bay selected"} tone="cyan" />
                  </div>
                </div>
                <div className="grid grid-2">
                  <DeviceFact label="Camera" value={config.cameraLabel} />
                  <DeviceFact label="Channel" value={config.cameraId} />
                  <DeviceFact label="Resolution" value="1920 x 1080" />
                  <DeviceFact label="Frame rate" value="30 fps" />
                </div>
              </div>
            </Panel>

            {mode === "sewing" ? (
              <Panel title="IoT Control Device" eyebrow="Sewing only" action={<StatusPill label="Paired" tone="ok" pulse />}>
                <div className="panel-body grid">
                  <div className="grid grid-2">
                    <DeviceFact label="Device" value="ESP32-WROOM" />
                    <DeviceFact label="IP address" value="192.168.1.105" />
                    <DeviceFact label="Rework button" value="Ready" />
                    <DeviceFact label="Downtime button" value="Ready" />
                  </div>
                  <StatusPill label="Two operator actions mapped: rework and downtime" tone="ok" />
                </div>
              </Panel>
            ) : (
              <Panel title="Production Specification" eyebrow="Quality mode" action={<StatusPill label="Active" tone="info" />}>
                <div className="panel-body grid">
                  <label className="field">
                    <span className="meta-label">Active spec</span>
                    <select className="select" value={specId} onChange={event => setSpecId(event.target.value)}>
                      {PRODUCTION_SPECS.map(spec => (
                        <option key={spec.specId} value={spec.specId}>
                          {spec.specLabel} | {spec.expectedStyle}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="panel" style={{ boxShadow: "none", padding: 16 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <div className="brand-mark"><Shirt size={20} /></div>
                        <div>
                          <div className="meta-label">Selected production profile</div>
                          <strong>{selectedSpec.specLabel}</strong>
                        </div>
                      </div>
                      <StatusPill label="Ready for scan" tone="ok" />
                    </div>

                    <div className="segmented" style={{ marginTop: 14 }}>
                      <StatusPill label={selectedSpec.expectedStyle} tone="info" />
                      <StatusPill label={`Size ${selectedSpec.expectedSize}`} tone="cyan" />
                      <StatusPill label={selectedSpec.expectedColours.join(", ")} tone="ok" />
                      <StatusPill label={`+/-${selectedSpec.widthToleranceCm} cm`} tone="warn" />
                    </div>

                    <div style={{ marginTop: 14, display: "grid", gap: 10 }}>
                      <SpecCheckRow label="Vision checks" value="Style, colour, and size match" />
                      <SpecCheckRow label="Measurement rule" value={`Width +/-${selectedSpec.widthToleranceCm} cm, height +/-${selectedSpec.heightToleranceCm} cm`} />
                      <SpecCheckRow label="Inspection output" value="Pass, rework, or mismatch decision" />
                    </div>
                  </div>
                </div>
              </Panel>
            )}
          </div>
        )}

        {step === 3 && mode && (
          <div className="grid grid-2">
            <Panel title="Operator Session" eyebrow="Required">
              <div className="panel-body grid">
                <label className="field">
                  <span className="meta-label">Operator name</span>
                  <input className="input" value={operator} onChange={event => setOperator(event.target.value)} placeholder="Enter operator name" autoFocus />
                </label>
                <DeviceFact label="Station" value={config.stationLabel} />
              </div>
            </Panel>

            <Panel title="Shift Parameters" eyebrow={mode === "sewing" ? "Production target" : "Inspection spec"}>
              <div className="panel-body grid">
                {mode === "sewing" ? (
                  <label className="field">
                    <span className="meta-label">Shift piece target</span>
                    <input className="input" type="number" min={1} max={500} value={target} onChange={event => setTarget(Number(event.target.value))} />
                  </label>
                ) : (
                  <DeviceFact label="Active spec" value={`${selectedSpec.specLabel} | ${selectedSpec.expectedStyle} ${selectedSpec.expectedSize}`} />
                )}
                <StatusPill label={mode === "sewing" ? "Sewing dashboard will load" : "Quality dashboard will load"} tone="cyan" />
              </div>
            </Panel>
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "space-between", gap: 10, marginTop: 20 }}>
          <button className="btn" onClick={back}><ArrowLeft size={16} /> Back</button>
          <button className={step === 3 ? "btn btn-success" : "btn btn-primary"} onClick={next}>
            {step === 3 ? <UserRound size={16} /> : null}
            {step === 3 ? "Start Session" : "Continue"}
            <ArrowRight size={16} />
          </button>
        </div>
      </section>
    </main>
  );
}

function DeviceFact({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="panel" style={{ boxShadow: "none", padding: 14 }}>
      <div className="meta-label">{label}</div>
      <strong>{value}</strong>
    </div>
  );
}

function SpecCheckRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, borderTop: "1px solid var(--line-soft)", paddingTop: 10 }}>
      <span className="muted">{label}</span>
      <strong style={{ textAlign: "right" }}>{value}</strong>
    </div>
  );
}
