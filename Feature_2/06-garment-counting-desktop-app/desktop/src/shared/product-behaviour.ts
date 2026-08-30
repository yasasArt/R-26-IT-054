import type { OperatorMode, SessionMode, SewingState } from "./types";

export const CLASSIFIER_STATES = ["IDLE_SETUP", "SEWING"] as const satisfies readonly SewingState[];

export const WORKSTATION_CLASS = "workstation" as const;

export const OPERATOR_MODES = ["NORMAL", "REWORK", "DOWNTIME"] as const satisfies readonly OperatorMode[];

export const SESSION_MODES = ["PRODUCTION", "VALIDATION"] as const satisfies readonly SessionMode[];

export const COUNT_TRANSITION = {
  from: "SEWING",
  to: "IDLE_SETUP",
} as const satisfies { from: SewingState; to: SewingState };

export const INFERENCE_DEFAULTS = {
  clipDurationSeconds: 1.5,
  framesPerClip: 8,
  classifierInputSize: 224,
  workstationInputSize: 640,
  predictionIntervalSeconds: 0.3,
  smoothingWindowSize: 5,
  minimumConfidence: 0.55,
  minimumSewingDurationSeconds: 2,
  minimumIdleDurationSeconds: 0.6,
  cooldownSeconds: 3,
} as const;

export const PHYSICAL_RESET_ACTION = "RETURN_TO_NORMAL" as const;

export function hasExpectedWorkstationClass(classNames: readonly string[]): boolean {
  return classNames.length === 1 && classNames[0] === WORKSTATION_CLASS;
}

export function hasExpectedClassifierStates(classNames: readonly string[]): boolean {
  return (
    classNames.length === CLASSIFIER_STATES.length &&
    CLASSIFIER_STATES.every((state, index) => classNames[index] === state)
  );
}
