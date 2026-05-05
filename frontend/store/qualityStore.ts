// store/qualityStore.ts
import { create } from "zustand";
import type {
  CameraStatus,
  IGarmentAnalysis, IInspectionRecord,
  IProductionSpec, ICalibrationData,
} from "@/lib/types";
import { generateId } from "@/lib/utils";
import { PRODUCTION_SPECS, QUALITY } from "@/lib/constants";

interface QualityState {
  approvedCount:  number;
  reworkCount:    number;
  mismatchCount:  number;
  currentGarment: IGarmentAnalysis | null;
  isAnalysing:    boolean;
  cameraStatus:   CameraStatus;
  calibration:    ICalibrationData;
  activeSpec:     IProductionSpec;
  inspectionLog:  IInspectionRecord[];
  isSimulating:   boolean;

  recordInspection: (analysis: IGarmentAnalysis) => void;
  setCurrentGarment: (g: IGarmentAnalysis | null) => void;
  setIsAnalysing:  (v: boolean) => void;
  setCameraStatus: (s: CameraStatus) => void;
  setCalibration:  (d: Partial<ICalibrationData>) => void;
  setActiveSpec:   (s: IProductionSpec) => void;
  setSimulating:   (v: boolean) => void;
  resetQualityState: () => void;
}

const INITIAL_CALIBRATION: ICalibrationData = {
  status:                  "calibrated",
  referenceObjectSizeCm:   10.0,
  pixelPerCmRatio:         18.4,
  lastCalibratedAt:        new Date(),
  cameraId:                "cam-0",
};

const INITIAL_STATE = {
  approvedCount:  0,
  reworkCount:    0,
  mismatchCount:  0,
  currentGarment: null as IGarmentAnalysis | null,
  isAnalysing:    false,
  cameraStatus:   "live" as CameraStatus,
  calibration:    INITIAL_CALIBRATION,
  activeSpec:     PRODUCTION_SPECS[0],
  inspectionLog:  [] as IInspectionRecord[],
  isSimulating:   false,
};

export const useQualityStore = create<QualityState>()((set, get) => ({
  ...INITIAL_STATE,

  recordInspection: (analysis) => {
    const { activeSpec } = get();

    const record: IInspectionRecord = {
      id:              generateId("insp"),
      timestamp:       analysis.timestamp,
      garmentAnalysis: analysis,
      decision:        analysis.decision,
      specLabel:       activeSpec.specLabel,   // ← fixed: use active spec label
    };

    set(state => {
      const newLog = [record, ...state.inspectionLog].slice(0, QUALITY.INSPECTION_LOG_MAX);
      return {
        approvedCount:  analysis.decision === "PASS"     ? state.approvedCount  + 1 : state.approvedCount,
        reworkCount:    analysis.decision === "REWORK"   ? state.reworkCount    + 1 : state.reworkCount,
        mismatchCount:  analysis.decision === "MISMATCH" ? state.mismatchCount  + 1 : state.mismatchCount,
        currentGarment: analysis,
        inspectionLog:  newLog,
        isAnalysing:    false,
      };
    });
  },

  setCurrentGarment: (g)    => set({ currentGarment: g }),
  setIsAnalysing:    (v)    => set({ isAnalysing: v }),
  setCameraStatus:   (s)    => set({ cameraStatus: s }),
  setCalibration:    (d)    => set(state => ({ calibration: { ...state.calibration, ...d } })),
  setActiveSpec:     (s)    => set({ activeSpec: s }),
  setSimulating:     (v)    => set({ isSimulating: v }),
  resetQualityState: ()     => set(INITIAL_STATE),
}));