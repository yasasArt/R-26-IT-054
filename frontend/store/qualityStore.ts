// store/qualityStore.ts
import { create } from "zustand";
import type {
  CameraStatus,
  CalibrationStatus,
  IGarmentAnalysis,
  IInspectionRecord,
  IProductionSpec,
  ICalibrationData,
} from "@/lib/types";
import { generateId } from "@/lib/utils";
import { PRODUCTION_SPECS, QUALITY } from "@/lib/constants";

interface QualityState {
  // ── Counters ──
  approvedCount: number;
  reworkCount: number;
  mismatchCount: number;

  // ── Current analysis ──
  currentGarment: IGarmentAnalysis | null;
  isAnalysing: boolean;

  // ── Device status ──
  cameraStatus: CameraStatus;
  calibration: ICalibrationData;

  // ── Production spec ──
  activeSpec: IProductionSpec;

  // ── History ──
  inspectionLog: IInspectionRecord[];

  // ── Simulation ──
  isSimulating: boolean;

  // ── Actions ──
  recordInspection: (analysis: IGarmentAnalysis) => void;
  setCurrentGarment: (garment: IGarmentAnalysis | null) => void;
  setIsAnalysing: (val: boolean) => void;
  setCameraStatus: (status: CameraStatus) => void;
  setCalibration: (data: Partial<ICalibrationData>) => void;
  setActiveSpec: (spec: IProductionSpec) => void;
  setSimulating: (val: boolean) => void;
  resetQualityState: () => void;
}

const INITIAL_CALIBRATION: ICalibrationData = {
  status: "calibrated",
  referenceObjectSizeCm: 10.0,
  pixelPerCmRatio: 18.4,
  lastCalibratedAt: new Date(),
  cameraId: "cam-0",
};

const INITIAL_STATE = {
  approvedCount: 0,
  reworkCount: 0,
  mismatchCount: 0,
  currentGarment: null as IGarmentAnalysis | null,
  isAnalysing: false,
  cameraStatus: "live" as CameraStatus,
  calibration: INITIAL_CALIBRATION,
  activeSpec: PRODUCTION_SPECS[0],
  inspectionLog: [] as IInspectionRecord[],
  isSimulating: false,
};

export const useQualityStore = create<QualityState>()((set) => ({
  ...INITIAL_STATE,

  recordInspection: (analysis) => {
    const record: IInspectionRecord = {
      id: generateId("insp"),
      timestamp: analysis.timestamp,
      garmentAnalysis: analysis,
      decision: analysis.decision,
      specLabel: analysis.specMatchResults.length > 0
        ? (analysis.specMatchResults[0]?.expected ?? "Unknown")
        : "Unknown",
    };

    set((state) => {
      const newLog = [record, ...state.inspectionLog].slice(
        0,
        QUALITY.INSPECTION_LOG_MAX
      );

      return {
        approvedCount:
          analysis.decision === "PASS"
            ? state.approvedCount + 1
            : state.approvedCount,
        reworkCount:
          analysis.decision === "REWORK"
            ? state.reworkCount + 1
            : state.reworkCount,
        mismatchCount:
          analysis.decision === "MISMATCH"
            ? state.mismatchCount + 1
            : state.mismatchCount,
        currentGarment: analysis,
        inspectionLog: newLog,
        isAnalysing: false,
      };
    });
  },

  setCurrentGarment: (garment) => set({ currentGarment: garment }),

  setIsAnalysing: (val) => set({ isAnalysing: val }),

  setCameraStatus: (status) => set({ cameraStatus: status }),

  setCalibration: (data) =>
    set((state) => ({
      calibration: { ...state.calibration, ...data },
    })),

  setActiveSpec: (spec) => set({ activeSpec: spec }),

  setSimulating: (val) => set({ isSimulating: val }),

  resetQualityState: () => set(INITIAL_STATE),
}));