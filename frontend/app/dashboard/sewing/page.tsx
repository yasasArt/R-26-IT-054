"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Boxes,
  CheckCircle2,
  Download,
  Eye,
  Gauge,
  Pause,
  Play,
  RotateCcw,
  Scissors,
  ShieldCheck,
  Timer,
  TrendingUp,
} from "lucide-react";
import { CameraFrame, DataTable, MetricCard, PageHeader, Panel, StatusPill } from "@/components/industrial/Primitives";
import { formatDuration, formatTime } from "@/lib/utils";

type WorkflowState = "idle_setup" | "sewing" | "put_aside" | "rest_pause";
type Visibility = "clear" | "partial" | "blocked";
type DecisionTone = "accepted" | "rejected" | "observed";

interface DemoStep {
  state: WorkflowState;
  duration: number;
  confidence: number;
  visibility: Visibility;
  garmentMotion: boolean;
  note: string;
}

interface CycleRecord {
  id: number;
  piece: number;
  startedAt: number;
  completedAt: number;
  cycleTime: number;
  pieceToPieceTime: number | null;
  confidence: number;
  visibility: Visibility;
}

interface TransitionRecord {
  id: number;
  timestamp: number;
  from: WorkflowState;
  to: WorkflowState;
  confidence: number;
  visibility: Visibility;
  decision: DecisionTone;
  reason: string;
}

interface SessionState {
  isRunning: boolean;
  speed: number;
  stepIndex: number;
  secondInStep: number;
  elapsedSeconds: number;
  currentState: WorkflowState;
  previousState: WorkflowState;
  activeCycleStart: number | null;
  lastPutAsideAt: number | null;
  pieceCount: number;
  cycles: CycleRecord[];
  transitions: TransitionRecord[];
  rejectedCounts: number;
}

const TARGET_CYCLE_SECONDS = 45;
const WARNING_CYCLE_SECONDS = 62;
const MIN_CONFIDENCE = 0.72;
const INITIAL_PIECES = 18;

const DEMO_STEPS: DemoStep[] = [
  { state: "idle_setup", duration: 8, confidence: 0.93, visibility: "clear", garmentMotion: false, note: "Operator aligns the next garment near the needle area." },
  { state: "sewing", duration: 24, confidence: 0.94, visibility: "clear", garmentMotion: true, note: "Active sewing around the machine work area." },
  { state: "put_aside", duration: 5, confidence: 0.91, visibility: "partial", garmentMotion: true, note: "Finished garment leaves the work area." },
  { state: "idle_setup", duration: 7, confidence: 0.89, visibility: "clear", garmentMotion: false, note: "New piece setup begins." },
  { state: "sewing", duration: 29, confidence: 0.88, visibility: "partial", garmentMotion: true, note: "Sewing continues with occasional head occlusion." },
  { state: "rest_pause", duration: 7, confidence: 0.77, visibility: "partial", garmentMotion: false, note: "Short pause after machine activity; no outgoing garment transfer." },
  { state: "sewing", duration: 12, confidence: 0.84, visibility: "clear", garmentMotion: true, note: "Operator resumes the same piece." },
  { state: "put_aside", duration: 4, confidence: 0.87, visibility: "clear", garmentMotion: true, note: "Valid completion after the sewing state resumes." },
  { state: "rest_pause", duration: 8, confidence: 0.81, visibility: "clear", garmentMotion: false, note: "Hands still; counted cycle is closed." },
  { state: "put_aside", duration: 3, confidence: 0.54, visibility: "blocked", garmentMotion: false, note: "Pile adjustment under occlusion, rejected by transition logic." },
  { state: "idle_setup", duration: 7, confidence: 0.86, visibility: "partial", garmentMotion: false, note: "Setup after suspicious movement." },
  { state: "sewing", duration: 20, confidence: 0.91, visibility: "clear", garmentMotion: true, note: "Stable productive sewing." },
  { state: "put_aside", duration: 4, confidence: 0.83, visibility: "partial", garmentMotion: true, note: "Count accepted with partial visibility warning." },
  { state: "idle_setup", duration: 6, confidence: 0.92, visibility: "clear", garmentMotion: false, note: "Preparing next garment." },
  { state: "sewing", duration: 32, confidence: 0.96, visibility: "clear", garmentMotion: true, note: "Longer but stable cycle." },
  { state: "put_aside", duration: 5, confidence: 0.95, visibility: "clear", garmentMotion: true, note: "High-confidence completion." },
];

const SEED_CYCLES: CycleRecord[] = [
  { id: 1, piece: 10, startedAt: 0, completedAt: 39, cycleTime: 39, pieceToPieceTime: 44, confidence: 0.92, visibility: "clear" },
  { id: 2, piece: 11, startedAt: 51, completedAt: 96, cycleTime: 45, pieceToPieceTime: 57, confidence: 0.9, visibility: "partial" },
  { id: 3, piece: 12, startedAt: 109, completedAt: 161, cycleTime: 52, pieceToPieceTime: 65, confidence: 0.87, visibility: "clear" },
  { id: 4, piece: 13, startedAt: 174, completedAt: 215, cycleTime: 41, pieceToPieceTime: 54, confidence: 0.94, visibility: "clear" },
  { id: 5, piece: 14, startedAt: 229, completedAt: 289, cycleTime: 60, pieceToPieceTime: 74, confidence: 0.79, visibility: "partial" },
  { id: 6, piece: 15, startedAt: 305, completedAt: 348, cycleTime: 43, pieceToPieceTime: 59, confidence: 0.91, visibility: "clear" },
  { id: 7, piece: 16, startedAt: 363, completedAt: 416, cycleTime: 53, pieceToPieceTime: 68, confidence: 0.88, visibility: "partial" },
  { id: 8, piece: 17, startedAt: 432, completedAt: 472, cycleTime: 40, pieceToPieceTime: 56, confidence: 0.96, visibility: "clear" },
  { id: 9, piece: 18, startedAt: 489, completedAt: 536, cycleTime: 47, pieceToPieceTime: 64, confidence: 0.9, visibility: "clear" },
];

const STATE_META: Record<WorkflowState, { label: string; short: string; tone: "ok" | "warn" | "info" | "cyan" | "orange" | "muted"; icon: typeof Activity }> = {
  idle_setup: { label: "Idle setup", short: "Setup", tone: "info", icon: Boxes },
  sewing: { label: "Sewing", short: "Sewing", tone: "ok", icon: Scissors },
  put_aside: { label: "Put aside", short: "Transfer", tone: "cyan", icon: CheckCircle2 },
  rest_pause: { label: "Rest pause", short: "Pause", tone: "orange", icon: Pause },
};

function createInitialState(): SessionState {
  return {
    isRunning: true,
    speed: 1,
    stepIndex: 0,
    secondInStep: 0,
    elapsedSeconds: 12 * 60 + 16,
    currentState: "idle_setup",
    previousState: "idle_setup",
    activeCycleStart: null,
    lastPutAsideAt: 536,
    pieceCount: INITIAL_PIECES,
    cycles: SEED_CYCLES,
    transitions: [
      {
        id: 1,
        timestamp: 536,
        from: "sewing",
        to: "put_aside",
        confidence: 0.9,
        visibility: "clear",
        decision: "accepted",
        reason: "Validated sewing -> put_aside transition.",
      },
    ],
    rejectedCounts: 2,
  };
}

export default function SewingDashboardPage() {
  const [session, setSession] = useState<SessionState>(() => createInitialState());
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const currentStep = DEMO_STEPS[session.stepIndex];
  const latestCycle = session.cycles.at(-1);
  const averageCycle = useMemo(() => {
    const cycles = session.cycles.slice(-12);
    return cycles.reduce((sum, cycle) => sum + cycle.cycleTime, 0) / cycles.length;
  }, [session.cycles]);
  const modelStatus = currentStep.confidence >= MIN_CONFIDENCE && currentStep.visibility !== "blocked" ? "Decision ready" : "Gated";
  const currentCycleSeconds = session.activeCycleStart === null ? 0 : Math.max(session.elapsedSeconds - session.activeCycleStart, 0);
  const productivityRate = Math.round((3600 / Math.max(averageCycle || TARGET_CYCLE_SECONDS, 1)) * 10) / 10;
  const stateIcon = STATE_META[session.currentState].icon;
  const projection = Math.max(0, 60 - session.pieceCount);
  const recentCycles = session.cycles.slice(-12);
  const recentSlowCycles = recentCycles.filter((cycle) => cycle.cycleTime > TARGET_CYCLE_SECONDS).length;
  const recentFastestCycle = recentCycles.length ? Math.min(...recentCycles.map((cycle) => cycle.cycleTime)) : 0;
  const recentAverageConfidence = recentCycles.length
    ? Math.round((recentCycles.reduce((sum, cycle) => sum + cycle.confidence, 0) / recentCycles.length) * 100)
    : 0;

  useEffect(() => {
    if (!session.isRunning) {
      if (tickRef.current) clearInterval(tickRef.current);
      return;
    }

    tickRef.current = setInterval(() => {
      setSession((prev) => advanceSession(prev));
    }, 1000 / session.speed);

    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
    };
  }, [session.isRunning, session.speed]);

  function resetDemo() {
    setSession(createInitialState());
  }

  function jumpToUncertainty() {
    setSession((prev) => ({
      ...prev,
      stepIndex: 9,
      secondInStep: 0,
      currentState: DEMO_STEPS[9].state,
      previousState: "rest_pause",
      elapsedSeconds: prev.elapsedSeconds + 1,
    }));
  }

  function exportCsv() {
    const header = "piece,cycle_time_seconds,piece_to_piece_seconds,confidence,visibility,completed_at_seconds";
    const rows = session.cycles.map((cycle) =>
      [cycle.piece, cycle.cycleTime, cycle.pieceToPieceTime ?? "", cycle.confidence.toFixed(2), cycle.visibility, cycle.completedAt].join(",")
    );
    const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "sewing_state_dashboard_demo.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="animate-in sewing-upgrade">
      <PageHeader
        eyebrow="State workflow prototype | Frontend demo"
        title="Sewing workstation intelligence"
        description="State-based garment counting prototype using idle_setup, sewing, put_aside, and rest_pause transitions. Counts are accepted only when a stable sewing to put_aside completion is validated."
        actions={
          <div className="dashboard-actions">
            <StatusPill label={modelStatus} tone={modelStatus === "Decision ready" ? "ok" : "warn"} pulse={session.isRunning} />
            <button className="btn" onClick={() => setSession((prev) => ({ ...prev, isRunning: !prev.isRunning }))}>
              {session.isRunning ? <Pause size={16} /> : <Play size={16} />}
              {session.isRunning ? "Pause" : "Run"}
            </button>
            <button className="btn" onClick={resetDemo}>
              <RotateCcw size={16} />
              Reset
            </button>
          </div>
        }
      />

      <div className="state-kpi-grid">
        <StateMetric icon={stateIcon} label="Live state" value={STATE_META[session.currentState].label} tone={STATE_META[session.currentState].tone} sub={currentStep.note} />
        <MetricCard label="Validated pieces" value={session.pieceCount} sub={`${projection} pcs remaining | transition gated`} tone="ok" badge="gated" />
        <MetricCard label="Latest cycle" value={latestCycle?.cycleTime ?? "—"} unit={latestCycle ? "s" : ""} sub={`Primary: put_aside_start - sewing_start`} tone={cycleTone(latestCycle?.cycleTime ?? 0)} />
        <MetricCard label="Average cycle" value={averageCycle.toFixed(1)} unit="s" sub={`${productivityRate} pcs/hour current pace`} tone="cyan" />
      </div>

      <div className="grid monitor-grid sewing-workflow-grid">
        <Panel
          title="Live State Video Overlay"
          eyebrow="Garment + pose + temporal state"
          action={<StatusPill label={STATE_META[session.currentState].label} tone={STATE_META[session.currentState].tone} pulse />}
          className="span-2"
        >
          <CameraFrame mode="sewing">
            <div className={`state-video state-${session.currentState}`}>
              <div className="machine-bed">
                <div className="needle" />
                <span>Machine area</span>
              </div>
              <div className={`garment-blob ${currentStep.garmentMotion ? "moving" : ""}`} />
              <div className="pose-line arm-left" />
              <div className="pose-line arm-right" />
              <div className="pose-dot shoulder" />
              <div className="pose-dot wrist" />
              <div className={`garment-box visibility-${currentStep.visibility}`}>
                <span>Garment track</span>
              </div>
              <div className="state-label-card">
                <span>{STATE_META[session.currentState].short}</span>
                <strong>{Math.round(currentStep.confidence * 100)}%</strong>
              </div>
              {currentStep.visibility !== "clear" && (
                <div className={`occlusion-band visibility-${currentStep.visibility}`}>
                  <Eye size={16} />
                  {visibilityLabel(currentStep.visibility)}
                </div>
              )}
            </div>
            <div className="camera-caption">
              <StatusPill label={`state ${session.currentState}`} tone={STATE_META[session.currentState].tone} />
              <StatusPill label={`motion ${currentStep.garmentMotion ? "confirmed" : "none"}`} tone={currentStep.garmentMotion ? "ok" : "muted"} />
              <StatusPill label={`min confidence ${Math.round(MIN_CONFIDENCE * 100)}%`} tone="info" />
            </div>
          </CameraFrame>
        </Panel>

        <div className="grid live-monitor-support span-2">
          <Panel title="Transition Decision Engine" eyebrow="False-count prevention" action={<ShieldCheck size={18} className="ok" />}>
            <div className="decision-stack">
              <RuleRow label="Required transition" value="sewing -> put_aside" active={session.previousState === "sewing" && session.currentState === "put_aside"} />
              <RuleRow label="Confidence gate" value={`${Math.round(currentStep.confidence * 100)}% / ${Math.round(MIN_CONFIDENCE * 100)}%`} active={currentStep.confidence >= MIN_CONFIDENCE} />
              <RuleRow label="Visibility gate" value={visibilityLabel(currentStep.visibility)} active={currentStep.visibility !== "blocked"} />
              <RuleRow label="Garment motion" value={currentStep.garmentMotion ? "Outgoing transfer" : "No new transfer"} active={currentStep.garmentMotion} />
              <RuleRow label="Cooldown" value="Await next sewing state" active={session.currentState !== "put_aside" || session.previousState === "sewing"} />
            </div>
          </Panel>

          <Panel title="Current Cycle" eyebrow="Live timing">
            <div className="cycle-meter">
              <div className={`cycle-ring ${cycleTone(currentCycleSeconds)}`}>
                <span>{currentCycleSeconds || "—"}</span>
                <small>{currentCycleSeconds ? "sec" : "waiting"}</small>
              </div>
              <div className="cycle-meter-copy">
                <strong>{session.activeCycleStart === null ? "No active garment cycle" : "Timing current garment"}</strong>
                <span>{session.activeCycleStart === null ? "Timer starts when stable sewing begins." : "Timer closes only on accepted put_aside."}</span>
              </div>
            </div>
          </Panel>
        </div>
      </div>

      <div className="grid workflow-side-grid">
        <Panel title="Recent Counting Decisions" eyebrow="What the system accepted or rejected" className="span-2">
          <div className="timeline-strip">
            {session.transitions.slice(0, 9).map((transition) => (
              <div key={transition.id} className={`timeline-event ${transition.decision}`}>
                <span>{formatClock(transition.timestamp)}</span>
                <strong>{STATE_META[transition.from].short} to {STATE_META[transition.to].short}</strong>
                <small>{transition.reason}</small>
              </div>
            ))}
          </div>
        </Panel>

        {/* <Panel title="Count Quality Checks" eyebrow="Reasons a count can be trusted">
          <div className="warning-list">
            <WarningRow icon={<AlertTriangle size={17} />} label="Rejected false counts" value={session.rejectedCounts} tone="warn" />
            <WarningRow icon={<Eye size={17} />} label="Visibility now" value={visibilityLabel(currentStep.visibility)} tone={currentStep.visibility === "blocked" ? "bad" : currentStep.visibility === "partial" ? "warn" : "ok"} />
            <WarningRow icon={<Gauge size={17} />} label="Decision confidence" value={`${Math.round(currentStep.confidence * 100)}%`} tone={currentStep.confidence >= MIN_CONFIDENCE ? "ok" : "warn"} />
          </div>
        </Panel> */}
      </div>

      <div className="grid grid-3 analytics-grid">
        <Panel title="Cycle Time by Piece" eyebrow="Lower bars mean faster sewing" className="span-2">
          <CycleTrend cycles={recentCycles} />
        </Panel>
        <Panel title="Count Growth" eyebrow="Each step is one accepted garment">
          <CountTrend cycles={session.cycles.slice(-10)} target={60} />
        </Panel>
      </div>

      <div className="grid grid-3 analytics-grid">
        <Panel title="Session Statistics" eyebrow="Plain production summary">
          <div className="stat-list">
            <SummaryRow label="Elapsed time" value={formatDuration(session.elapsedSeconds)} />
            <SummaryRow label="Accepted transitions" value={session.cycles.length} />
            <SummaryRow label="Fastest recent cycle" value={recentFastestCycle ? `${recentFastestCycle}s` : "—"} />
            <SummaryRow label="Slow recent cycles" value={`${recentSlowCycles} of ${recentCycles.length}`} />
            <SummaryRow label="Target cycle" value={`${TARGET_CYCLE_SECONDS}s`} />
          </div>
        </Panel>

        <Panel title="Prototype Controls" eyebrow="Frontend only">
          <div className="control-grid">
            <button className="btn" onClick={() => setSession((prev) => ({ ...prev, speed: prev.speed === 1 ? 2 : 1 }))}>
              <TrendingUp size={16} />
              {session.speed === 1 ? "Run 2x" : "Run 1x"}
            </button>
            <button className="btn btn-danger" onClick={jumpToUncertainty}>
              <AlertTriangle size={16} />
              Show Gate
            </button>
            <button className="btn btn-primary" onClick={exportCsv}>
              <Download size={16} />
              Export CSV
            </button>
          </div>
        </Panel>

        <Panel title="Admin Snapshot" eyebrow="Model and thresholds">
          <div className="stat-list">
            <SummaryRow label="Model version" value="state-v0.3-demo" />
            <SummaryRow label="Video source" value="Overhead CAM-01" />
            <SummaryRow label="State window" value="1.5s stable" />
            <SummaryRow label="Recent confidence" value={recentAverageConfidence ? `${recentAverageConfidence}%` : "—"} />
          </div>
        </Panel>
      </div>

      <div className="analytics-grid">
        <Panel title="Completed Cycle Records" eyebrow="Supervisor review log">
          <DataTable
            headers={["Piece", "Completed", "Cycle Time", "Piece-to-Piece", "Confidence", "Visibility", "Result"]}
            rows={session.cycles.slice(-8).reverse().map((cycle) => [
              `#${cycle.piece}`,
              formatClock(cycle.completedAt),
              `${cycle.cycleTime}s`,
              cycle.pieceToPieceTime ? `${cycle.pieceToPieceTime}s` : "—",
              `${Math.round(cycle.confidence * 100)}%`,
              visibilityLabel(cycle.visibility),
              <StatusPill key={cycle.id} label={cycle.cycleTime <= WARNING_CYCLE_SECONDS ? "accepted" : "slow"} tone={cycle.cycleTime <= WARNING_CYCLE_SECONDS ? "ok" : "warn"} />,
            ])}
          />
        </Panel>
      </div>
    </div>
  );
}

function advanceSession(prev: SessionState): SessionState {
  const step = DEMO_STEPS[prev.stepIndex];
  const nextSecondInStep = prev.secondInStep + 1;
  const elapsedSeconds = prev.elapsedSeconds + 1;

  if (nextSecondInStep < step.duration) {
    return {
      ...prev,
      secondInStep: nextSecondInStep,
      elapsedSeconds,
    };
  }

  const nextStepIndex = (prev.stepIndex + 1) % DEMO_STEPS.length;
  const nextStep = DEMO_STEPS[nextStepIndex];
  const from = step.state;
  const to = nextStep.state;
  let activeCycleStart = prev.activeCycleStart;
  let lastPutAsideAt = prev.lastPutAsideAt;
  let pieceCount = prev.pieceCount;
  let cycles = prev.cycles;
  let rejectedCounts = prev.rejectedCounts;
  let transition: TransitionRecord = {
    id: prev.transitions[0]?.id ? prev.transitions[0].id + 1 : 1,
    timestamp: elapsedSeconds,
    from,
    to,
    confidence: nextStep.confidence,
    visibility: nextStep.visibility,
    decision: "observed",
    reason: "Stable state transition observed.",
  };

  if (to === "sewing" && activeCycleStart === null) {
    activeCycleStart = elapsedSeconds;
    transition = { ...transition, reason: "Cycle timer started at stable sewing." };
  }

  if (to === "put_aside") {
    const hasValidTransition = from === "sewing";
    const passesConfidence = nextStep.confidence >= MIN_CONFIDENCE;
    const passesVisibility = nextStep.visibility !== "blocked";
    const hasGarmentMotion = nextStep.garmentMotion;

    if (hasValidTransition && passesConfidence && passesVisibility && hasGarmentMotion && activeCycleStart !== null) {
      const cycleTime = elapsedSeconds - activeCycleStart;
      const nextPiece = pieceCount + 1;
      const newCycle: CycleRecord = {
        id: nextPiece,
        piece: nextPiece,
        startedAt: activeCycleStart,
        completedAt: elapsedSeconds,
        cycleTime,
        pieceToPieceTime: lastPutAsideAt === null ? null : elapsedSeconds - lastPutAsideAt,
        confidence: nextStep.confidence,
        visibility: nextStep.visibility,
      };

      pieceCount = nextPiece;
      cycles = [...cycles, newCycle].slice(-40);
      activeCycleStart = null;
      lastPutAsideAt = elapsedSeconds;
      transition = {
        ...transition,
        decision: "accepted",
        reason: "Count accepted from stable sewing -> put_aside.",
      };
    } else {
      rejectedCounts += 1;
      transition = {
        ...transition,
        decision: "rejected",
        reason: rejectionReason(hasValidTransition, passesConfidence, passesVisibility, hasGarmentMotion),
      };
    }
  }

  if (to === "idle_setup" && from === "put_aside") {
    activeCycleStart = null;
  }

  return {
    ...prev,
    stepIndex: nextStepIndex,
    secondInStep: 0,
    elapsedSeconds,
    currentState: to,
    previousState: from,
    activeCycleStart,
    lastPutAsideAt,
    pieceCount,
    cycles,
    rejectedCounts,
    transitions: [transition, ...prev.transitions].slice(0, 24),
  };
}

function rejectionReason(hasValidTransition: boolean, passesConfidence: boolean, passesVisibility: boolean, hasGarmentMotion: boolean) {
  if (!hasValidTransition) return "Rejected: put_aside did not follow sewing.";
  if (!passesConfidence) return "Rejected: confidence below threshold.";
  if (!passesVisibility) return "Rejected: heavy occlusion blocked the decision.";
  if (!hasGarmentMotion) return "Rejected: no outgoing garment motion.";
  return "Rejected by cooldown or incomplete cycle context.";
}

function StateMetric({
  icon: Icon,
  label,
  value,
  sub,
  tone,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  sub: string;
  tone: "ok" | "warn" | "info" | "cyan" | "orange" | "muted";
}) {
  return (
    <article className="metric-card state-metric-card">
      <div className="metric-top">
        <div className="metric-label">{label}</div>
        <Icon size={20} className={tone} />
      </div>
      <div>
        <div className={`state-metric-value ${tone}`}>{value}</div>
        <div className="metric-sub">{sub}</div>
      </div>
    </article>
  );
}

function RuleRow({ label, value, active }: { label: string; value: string; active: boolean }) {
  return (
    <div className={`rule-row ${active ? "active" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function WarningRow({ icon, label, value, tone }: { icon: ReactNode; label: string; value: string | number; tone: "ok" | "warn" | "bad" }) {
  return (
    <div className="warning-row">
      <span className={tone}>{icon}</span>
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="summary-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function CycleTrend({ cycles }: { cycles: CycleRecord[] }) {
  const max = Math.max(...cycles.map((cycle) => cycle.cycleTime), WARNING_CYCLE_SECONDS + 10);
  const average = cycles.length ? cycles.reduce((sum, cycle) => sum + cycle.cycleTime, 0) / cycles.length : 0;
  const latest = cycles.at(-1);

  return (
    <div className="chart-panel readable-chart">
      <div className="chart-summary-grid">
        <ChartInsight label="Best cycle" value={cycles.length ? `${Math.min(...cycles.map((cycle) => cycle.cycleTime))}s` : "—"} tone="ok" />
        <ChartInsight label="Average" value={average ? `${average.toFixed(1)}s` : "—"} tone={cycleTone(average)} />
        <ChartInsight label="Latest piece" value={latest ? `#${latest.piece} · ${latest.cycleTime}s` : "—"} tone={cycleTone(latest?.cycleTime ?? 0)} />
      </div>
      <div className="cycle-bars-chart" role="img" aria-label="Bar chart showing cycle seconds for each recent piece">
        <div className="cycle-target-line" style={{ bottom: `${(TARGET_CYCLE_SECONDS / max) * 100}%` }}>
          <span>Target {TARGET_CYCLE_SECONDS}s</span>
        </div>
        <div className="cycle-warning-line" style={{ bottom: `${(WARNING_CYCLE_SECONDS / max) * 100}%` }}>
          <span>Warning {WARNING_CYCLE_SECONDS}s</span>
        </div>
        {cycles.map((cycle) => (
          <div key={cycle.id} className="cycle-column">
            <div
              className={`cycle-bar-detailed ${cycleTone(cycle.cycleTime)}`}
              style={{ height: `${Math.max((cycle.cycleTime / max) * 100, 12)}%` }}
              title={`Piece #${cycle.piece}: ${cycle.cycleTime} seconds`}
            >
              <strong>{cycle.cycleTime}s</strong>
            </div>
            <span>#{cycle.piece}</span>
          </div>
        ))}
      </div>
      <div className="chart-legend">
        <span><Timer size={14} /> Green is on target</span>
        <span>Yellow needs attention</span>
        <span>Red is too slow</span>
      </div>
    </div>
  );
}

function CountTrend({ cycles, target }: { cycles: CycleRecord[]; target: number }) {
  const firstPiece = cycles[0]?.piece ?? INITIAL_PIECES;
  const latest = cycles.at(-1)?.piece ?? firstPiece;
  const progress = Math.min((latest / target) * 100, 100);

  return (
    <div className="chart-panel readable-chart">
      <div className="count-progress">
        <div>
          <span className="meta-label">Current total</span>
          <strong>{latest} pieces</strong>
        </div>
        <div>
          <span className="meta-label">Demo target</span>
          <strong>{target} pieces</strong>
        </div>
      </div>
      <div className="progress-track" aria-label={`${Math.round(progress)} percent of target complete`}>
        <div className="progress-fill" style={{ width: `${progress}%` }} />
        <span>{Math.round(progress)}%</span>
      </div>
      <div className="count-step-chart">
        {cycles.map((cycle) => (
          <div key={cycle.id} className="count-step">
            <strong>#{cycle.piece}</strong>
            <span>{formatClock(cycle.completedAt)}</span>
          </div>
        ))}
      </div>
      <div className="chart-legend">
        <span>Each block means one count was accepted after sewing.</span>
      </div>
    </div>
  );
}

function ChartInsight({ label, value, tone }: { label: string; value: string; tone: "ok" | "warn" | "bad" | "cyan" }) {
  return (
    <div className="chart-insight">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
    </div>
  );
}

function cycleTone(seconds: number): "ok" | "warn" | "bad" | "cyan" {
  if (!seconds) return "cyan";
  if (seconds <= TARGET_CYCLE_SECONDS) return "ok";
  if (seconds <= WARNING_CYCLE_SECONDS) return "warn";
  return "bad";
}

function visibilityLabel(visibility: Visibility) {
  return visibility === "clear" ? "Clear" : visibility === "partial" ? "Partial occlusion" : "Blocked";
}

function formatClock(seconds: number) {
  const date = new Date();
  date.setHours(8, 0, 0, 0);
  date.setSeconds(seconds);
  return formatTime(date);
}
