import type { InferenceStatus, SessionMode } from "./types";

type DisplayState = Pick<InferenceStatus, "running" | "phase" | "sewing_state"> | null;

export function describeSewingActivity(inference: DisplayState): string {
  if (!inference || !inference.running) return "Monitoring not started";
  if (inference.phase === "PAUSED") return "Counting paused";
  if (inference.sewing_state === "SEWING") return "Sewing in progress";
  if (inference.sewing_state === "IDLE_SETUP") return "Ready for next garment";
  if (inference.sewing_state === "INVALID_VIEW") return "Workstation not visible";
  return "Checking workstation";
}

export function allowsRecordedWorkstationVideo(sessionMode: SessionMode): boolean {
  return sessionMode === "VALIDATION" || sessionMode === "PRODUCTION";
}
