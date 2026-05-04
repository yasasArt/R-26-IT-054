// store/workstationStore.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AreaMode, IWorkstationConfig } from "@/lib/types";
import { DEFAULT_WORKSTATION_CONFIG } from "@/lib/constants";
import { generateId } from "@/lib/utils";

interface WorkstationState {
  // Configuration
  config: IWorkstationConfig;
  isConfigured: boolean;

  // Active session
  sessionId: string | null;
  sessionStartTime: Date | null;

  // Actions
  setMode: (mode: AreaMode) => void;
  setConfig: (config: Partial<IWorkstationConfig>) => void;
  startSession: (operatorName: string, mode: AreaMode) => void;
  endSession: () => void;
  resetWorkstation: () => void;
}

export const useWorkstationStore = create<WorkstationState>()(
  persist(
    (set) => ({
      config: DEFAULT_WORKSTATION_CONFIG,
      isConfigured: false,
      sessionId: null,
      sessionStartTime: null,

      setMode: (mode) =>
        set((state) => ({
          config: { ...state.config, mode },
        })),

      setConfig: (partial) =>
        set((state) => ({
          config: { ...state.config, ...partial },
        })),

      startSession: (operatorName, mode) =>
        set((state) => ({
          config: { ...state.config, operatorName, mode, shiftStart: new Date() },
          isConfigured: true,
          sessionId: generateId("sess"),
          sessionStartTime: new Date(),
        })),

      endSession: () =>
        set({
          isConfigured: false,
          sessionId: null,
          sessionStartTime: null,
          config: { ...DEFAULT_WORKSTATION_CONFIG },
        }),

      resetWorkstation: () =>
        set({
          config: DEFAULT_WORKSTATION_CONFIG,
          isConfigured: false,
          sessionId: null,
          sessionStartTime: null,
        }),
    }),
    {
      name: "vision-system-workstation",
      // Only persist config — not session runtime state
      partialize: (state) => ({
        config: {
          stationId: state.config.stationId,
          stationLabel: state.config.stationLabel,
          serverUrl: state.config.serverUrl,
          cameraId: state.config.cameraId,
          cameraLabel: state.config.cameraLabel,
        },
      }),
    }
  )
);