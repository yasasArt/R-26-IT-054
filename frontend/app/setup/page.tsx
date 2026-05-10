"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  CheckCircle2,
  Cpu,
  MonitorCog,
  Ruler,
  Shirt,
  UserRound,
} from "lucide-react";
import { APP_NAME, APP_SUBTITLE, PRODUCTION_SPECS, ROUTES } from "@/lib/constants";
import type { AreaMode } from "@/lib/types";
import { useQualityStore } from "@/store/qualityStore";
import { useWorkstationStore } from "@/store/workstationStore";
import { Panel, StatusPill } from "@/components/industrial/Primitives";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

type Step = 1 | 2 | 3;

type ModeMeta = {
  title: string;
  summary: string;
  badge: string;
  badgeTone: "ok" | "info" | "cyan";
  supportLabel: string;
  dashboardLabel: string;
  bestFor: string;
  visualTone: string;
};

const MODE_META: Record<AreaMode, ModeMeta> = {
  sewing: {
    title: "Sewing Operator Area",
    summary: "Monitor piece flow, cycle timing, and operator actions from the live workstation.",
    badge: "Camera + IoT",
    badgeTone: "ok",
    supportLabel: "ESP32 controls",
    dashboardLabel: "Production dashboard",
    bestFor: "Operator tracking",
    visualTone: "sewing",
  },
  quality: {
    title: "Quality Checker Area",
    summary: "Inspect garment specs, colour, and measurement checks from the quality station.",
    badge: "Camera only",
    badgeTone: "info",
    supportLabel: "Spec validation",
    dashboardLabel: "Inspection dashboard",
    bestFor: "Quality checking",
    visualTone: "quality",
  },
};

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
    <main className={`setup-page setup-page-step-${step}`}>
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

      <section className={`setup-main animate-in setup-main-step-${step}`}>
        <div className={`page-head setup-page-head ${step === 1 ? "setup-page-head-step1" : ""}`}>
          <div>
            <div className="eyebrow">Configuration wizard · Step {step} of 3</div>
            <h1 className="page-title">
              {step === 1 ? "Select workstation area mode" : step === 2 ? "Confirm local devices" : "Start production session"}
            </h1>
            <p className="page-description">
              {step === 1
                ? "Choose the production area so the workstation loads the correct live dashboard and controls."
                : step === 2
                  ? "Review connected camera and mode-specific devices before opening the live interface."
                  : "Confirm the operator and final session settings for this local prototype run."}
            </p>
          </div>
          {error && <StatusPill label={error} tone="bad" />}
        </div>

        {step === 1 && (
          <div className="setup-mode-grid setup-mode-grid-focused">
            {(["sewing", "quality"] as AreaMode[]).map(areaMode => {
              const meta = MODE_META[areaMode];
              const isSelected = mode === areaMode;

              return (
                <button
                  key={areaMode}
                  className={`panel mode-card mode-card-enhanced setup-mode-card ${isSelected ? "selected" : ""}`}
                  onClick={() => setMode(areaMode)}
                  type="button"
                >
                  <div className={`mode-visual mode-visual-${meta.visualTone}`}>
                    <div className="camera-overlay" />
                    <div className="mode-badge">
                      <StatusPill label={meta.badge} tone={meta.badgeTone} />
                    </div>
                    <div className="mode-select-indicator" aria-hidden="true">
                      {isSelected ? <CheckCircle2 size={18} /> : <div className="mode-select-ring" />}
                    </div>
                    {areaMode === "sewing" ? (
                      <>
                        <Shirt className="mode-main-icon" size={46} />
                        <Cpu className="mode-support-icon ok" size={18} />
                      </>
                    ) : (
                      <>
                        <Ruler className="mode-main-icon info" size={46} />
                        <Camera className="mode-support-icon cyan" size={18} />
                      </>
                    )}
                  </div>

                  <div className="panel-body setup-mode-card-body">
                    <div className="setup-mode-card-head">
                      <h2 className="panel-title">{meta.title}</h2>
                      <p className="muted">{meta.summary}</p>
                    </div>

                    <div className="setup-mode-meta-grid">
                      <div className="setup-mode-meta-item">
                        <span className="meta-label">Dashboard</span>
                        <strong>{meta.dashboardLabel}</strong>
                      </div>
                      <div className="setup-mode-meta-item">
                        <span className="meta-label">Support</span>
                        <strong>{meta.supportLabel}</strong>
                      </div>
                      <div className="setup-mode-meta-item setup-mode-meta-item-wide">
                        <span className="meta-label">Best for</span>
                        <strong>{meta.bestFor}</strong>
                      </div>
                    </div>

                    <div className="setup-mode-card-footer">
                      <span className={`setup-mode-selection ${isSelected ? "selected" : ""}`}>
                        {isSelected ? "Selected" : "Click to select"}
                      </span>
                      <ArrowRight size={16} />
                    </div>
                  </div>
                </button>
              );
            })}
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
                        <option key={spec.specId} value={spec.specId}>{spec.specLabel} | {spec.expectedStyle} {spec.expectedSize}</option>
                      ))}
                    </select>
                  </label>
                  <div className="grid grid-2">
                    <DeviceFact label="Style" value={selectedSpec.expectedStyle} />
                    <DeviceFact label="Size" value={selectedSpec.expectedSize} />
                    <DeviceFact label="Colour" value={selectedSpec.expectedColours.join(", ")} />
                    <DeviceFact label="Tolerance" value={`±${selectedSpec.widthToleranceCm} cm`} />
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

        <div className="setup-actions">
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
    <div className="panel device-fact">
      <div className="meta-label">{label}</div>
      <strong>{value}</strong>
    </div>
  );
}
