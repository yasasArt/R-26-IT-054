// store/sewingStore.ts
import { create } from "zustand";
import type {
  OperatorStatus,
  CameraStatus,
  IoTStatus,
  IDetectionEvent,
  ICycleRecord,
  IIoTEvent,
  IDualSignalState,
} from "@/lib/types";
import { generateId } from "@/lib/utils";
import { DETECTION } from "@/lib/constants";

interface SewingState {
  // ── Core counters ──
  pieceCount: number;
  currentCycleTimeSeconds: number;
  averageCycleTimeSeconds: number;

  // ── Operator & device status ──
  operatorStatus: OperatorStatus;
  cameraStatus: CameraStatus;
  iotStatus: IoTStatus;

  // ── Rework / Downtime ──
  reworkActive: boolean;
  reworkStartTime: Date | null;
  downtimeActive: boolean;
  downtimeStartTime: Date | null;
  totalDowntimeSeconds: number;
  totalReworkCount: number;

  // ── Dual-signal state (Feature 2 redesign) ──
  dualSignal: IDualSignalState;

  // ── History arrays ──
  detectionLog: IDetectionEvent[];   // capped at DETECTION.LOG_MAX_ENTRIES
  cycleHistory: ICycleRecord[];
  iotEvents: IIoTEvent[];

  // ── Simulation control ──
  isSimulating: boolean;

  // ── Actions ──
  incrementPiece: (event: Omit<IDetectionEvent, "id">) => void;
  updateCycleTime: (seconds: number) => void;
  setOperatorStatus: (status: OperatorStatus) => void;
  setCameraStatus: (status: CameraStatus) => void;
  setIoTStatus: (status: IoTStatus) => void;

  // Dual-signal
  setSignalA: (active: boolean) => void;
  setSignalB: (active: boolean) => void;
  resetDualSignal: () => void;

  // Rework / Downtime
  startRework: () => void;
  endRework: () => void;
  startDowntime: () => void;
  endDowntime: () => void;

  // Simulation
  setSimulating: (val: boolean) => void;

  // Reset
  resetSewingState: () => void;
}

const INITIAL_DUAL_SIGNAL: IDualSignalState = {
  signalA: "idle",
  signalATimestamp: null,
  signalB: "idle",
  signalBTimestamp: null,
  bothAgreed: false,
};

const INITIAL_STATE = {
  pieceCount: 0,
  currentCycleTimeSeconds: 0,
  averageCycleTimeSeconds: 0,
  operatorStatus: "idle" as OperatorStatus,
  cameraStatus: "live" as CameraStatus,
  iotStatus: "connected" as IoTStatus,
  reworkActive: false,
  reworkStartTime: null,
  downtimeActive: false,
  downtimeStartTime: null,
  totalDowntimeSeconds: 0,
  totalReworkCount: 0,
  dualSignal: INITIAL_DUAL_SIGNAL,
  detectionLog: [] as IDetectionEvent[],
  cycleHistory: [] as ICycleRecord[],
  iotEvents: [] as IIoTEvent[],
  isSimulating: false,
};

export const useSewingStore = create<SewingState>()((set, get) => ({
  ...INITIAL_STATE,

  incrementPiece: (eventData) => {
    const newEvent: IDetectionEvent = {
      ...eventData,
      id: generateId("det"),
    };

    const newCycleRecord: ICycleRecord = {
      id: generateId("cyc"),
      timestamp: newEvent.timestamp,
      pieceNumber: newEvent.pieceNumber,
      durationSeconds: newEvent.cycleTimeSeconds,
      isWithinTarget: newEvent.cycleTimeSeconds <= 45,
    };

    set((state) => {
      const newLog = [newEvent, ...state.detectionLog].slice(
        0,
        DETECTION.LOG_MAX_ENTRIES
      );
      const newHistory = [...state.cycleHistory, newCycleRecord].slice(-50);

      // Recalculate average
      const avg =
        newHistory.reduce((sum, r) => sum + r.durationSeconds, 0) /
        newHistory.length;

      return {
        pieceCount: state.pieceCount + 1,
        currentCycleTimeSeconds: newEvent.cycleTimeSeconds,
        averageCycleTimeSeconds: parseFloat(avg.toFixed(1)),
        detectionLog: newLog,
        cycleHistory: newHistory,
        operatorStatus: "active",
        dualSignal: INITIAL_DUAL_SIGNAL,
      };
    });
  },

  updateCycleTime: (seconds) => set({ currentCycleTimeSeconds: seconds }),

  setOperatorStatus: (status) => set({ operatorStatus: status }),

  setCameraStatus: (status) => set({ cameraStatus: status }),

  setIoTStatus: (status) => set({ iotStatus: status }),

  setSignalA: (active) =>
    set((state) => ({
      dualSignal: {
        ...state.dualSignal,
        signalA: active ? "triggered" : "idle",
        signalATimestamp: active ? new Date() : null,
        bothAgreed:
          active && state.dualSignal.signalB === "triggered",
      },
    })),

  setSignalB: (active) =>
    set((state) => ({
      dualSignal: {
        ...state.dualSignal,
        signalB: active ? "triggered" : "idle",
        signalBTimestamp: active ? new Date() : null,
        bothAgreed:
          active && state.dualSignal.signalA === "triggered",
      },
    })),

  resetDualSignal: () =>
    set({ dualSignal: INITIAL_DUAL_SIGNAL }),

  startRework: () => {
    if (get().reworkActive) return;
    const now = new Date();
    const newEvent: IIoTEvent = {
      id: generateId("iot"),
      timestamp: now,
      type: "rework_triggered",
      triggeredBy: "operator",
    };
    set((state) => ({
      reworkActive: true,
      reworkStartTime: now,
      operatorStatus: "rework",
      iotEvents: [newEvent, ...state.iotEvents],
    }));
  },

  endRework: () => {
    const state = get();
    if (!state.reworkActive) return;
    const durationSeconds = state.reworkStartTime
      ? Math.floor((Date.now() - state.reworkStartTime.getTime()) / 1000)
      : 0;
    const newEvent: IIoTEvent = {
      id: generateId("iot"),
      timestamp: new Date(),
      type: "rework_resolved",
      triggeredBy: "operator",
      durationSeconds,
    };
    set((s) => ({
      reworkActive: false,
      reworkStartTime: null,
      totalReworkCount: s.totalReworkCount + 1,
      operatorStatus: s.downtimeActive ? "downtime" : "active",
      iotEvents: [newEvent, ...s.iotEvents],
    }));
  },

  startDowntime: () => {
    if (get().downtimeActive) return;
    const now = new Date();
    const newEvent: IIoTEvent = {
      id: generateId("iot"),
      timestamp: now,
      type: "downtime_triggered",
      triggeredBy: "operator",
    };
    set((state) => ({
      downtimeActive: true,
      downtimeStartTime: now,
      operatorStatus: "downtime",
      iotEvents: [newEvent, ...state.iotEvents],
    }));
  },

  endDowntime: () => {
    const state = get();
    if (!state.downtimeActive) return;
    const durationSeconds = state.downtimeStartTime
      ? Math.floor((Date.now() - state.downtimeStartTime.getTime()) / 1000)
      : 0;
    const newEvent: IIoTEvent = {
      id: generateId("iot"),
      timestamp: new Date(),
      type: "downtime_resolved",
      triggeredBy: "operator",
      durationSeconds,
    };
    set((s) => ({
      downtimeActive: false,
      downtimeStartTime: null,
      totalDowntimeSeconds: s.totalDowntimeSeconds + durationSeconds,
      operatorStatus: s.reworkActive ? "rework" : "active",
      iotEvents: [newEvent, ...s.iotEvents],
    }));
  },

  setSimulating: (val) => set({ isSimulating: val }),

  resetSewingState: () => set(INITIAL_STATE),
}));
