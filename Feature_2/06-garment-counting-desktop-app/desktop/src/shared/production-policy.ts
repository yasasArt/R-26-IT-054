import type {
  CountingDecision,
  CountingPolicyInput,
  ProductionReadinessInput,
} from "./types";

export function getProductionBlockers(input: ProductionReadinessInput): string[] {
  const blockers: string[] = [];

  if (!input.backendReady) blockers.push("Python backend is not ready.");
  if (!input.garmentClassifierReady) blockers.push("Garment classifier is not loaded.");
  if (!input.workstationDetectorReady) blockers.push("Workstation detector is not loaded.");
  if (!input.cameraReady) blockers.push("Camera or validation video is not ready.");
  const simulationAllowed = input.sessionMode === "VALIDATION" && input.simulatedIotApproved === true;

  if (!simulationAllowed) {
    if (!input.iotConnected) blockers.push("IoT controller is not connected.");
    if (!input.iotNotificationsActive) blockers.push("IoT notifications are not active.");
  }

  return blockers;
}

export function canStartSession(input: ProductionReadinessInput): boolean {
  return getProductionBlockers(input).length === 0;
}

export function getCountingDecision(input: CountingPolicyInput): CountingDecision {
  if (!input.sessionActive) {
    return { permitted: false, reason: "NO_ACTIVE_SESSION" };
  }

  if (!input.workstationVisible) {
    return { permitted: false, reason: "INVALID_WORKSTATION_VIEW" };
  }

  const simulationAllowed = input.sessionMode === "VALIDATION" && input.simulatedIotApproved === true;

  if (!simulationAllowed && !input.iotConnected) {
    return { permitted: false, reason: "IOT_DISCONNECTED" };
  }

  if (!simulationAllowed && !input.iotNotificationsActive) {
    return { permitted: false, reason: "IOT_NOTIFICATIONS_INACTIVE" };
  }

  if (input.operatorMode === "REWORK") {
    return { permitted: false, reason: "REWORK_ACTIVE" };
  }

  if (input.operatorMode === "DOWNTIME") {
    return { permitted: false, reason: "DOWNTIME_ACTIVE" };
  }

  return { permitted: true, reason: "COUNTING_PERMITTED" };
}
