import assert from "node:assert/strict";
import test from "node:test";

import { canStartSession, getCountingDecision, getProductionBlockers } from "../src/shared/production-policy.ts";
import type { CountingPolicyInput, ProductionReadinessInput } from "../src/shared/types.ts";

const productionReady: ProductionReadinessInput = {
  sessionMode: "PRODUCTION",
  backendReady: true,
  garmentClassifierReady: true,
  workstationDetectorReady: true,
  cameraReady: true,
  workstationVisible: true,
  iotConnected: true,
  iotNotificationsActive: true,
};

const activeProduction: CountingPolicyInput = {
  sessionMode: "PRODUCTION",
  sessionActive: true,
  workstationVisible: true,
  iotConnected: true,
  iotNotificationsActive: true,
  operatorMode: "NORMAL",
};

test("production starts only when every real dependency is ready", () => {
  assert.equal(canStartSession(productionReady), true);
  assert.deepEqual(getProductionBlockers(productionReady), []);
});

test("production cannot bypass a disconnected physical controller", () => {
  const disconnected = {
    ...productionReady,
    iotConnected: false,
    iotNotificationsActive: false,
    simulatedIotApproved: true,
  } satisfies ProductionReadinessInput;

  assert.equal(canStartSession(disconnected), false);
  assert.deepEqual(getProductionBlockers(disconnected), [
    "IoT controller is not connected.",
    "IoT notifications are not active.",
  ]);
});

test("an explicitly approved validation session can simulate its controller", () => {
  const validation = {
    ...productionReady,
    sessionMode: "VALIDATION",
    iotConnected: false,
    iotNotificationsActive: false,
    simulatedIotApproved: true,
  } satisfies ProductionReadinessInput;

  assert.equal(canStartSession(validation), true);
});

test("a validation session without explicit simulation approval remains blocked", () => {
  assert.equal(
    canStartSession({
      ...productionReady,
      sessionMode: "VALIDATION",
      iotConnected: false,
      iotNotificationsActive: false,
    }),
    false,
  );
});

test("a tested camera can start production before the workstation view is verified", () => {
  assert.equal(canStartSession({ ...productionReady, workstationVisible: false }), true);
});

test("normal production permits counting", () => {
  assert.deepEqual(getCountingDecision(activeProduction), {
    permitted: true,
    reason: "COUNTING_PERMITTED",
  });
});

test("rework pauses counting without becoming downtime", () => {
  assert.deepEqual(getCountingDecision({ ...activeProduction, operatorMode: "REWORK" }), {
    permitted: false,
    reason: "REWORK_ACTIVE",
  });
});

test("downtime pauses counting without becoming rework", () => {
  assert.deepEqual(getCountingDecision({ ...activeProduction, operatorMode: "DOWNTIME" }), {
    permitted: false,
    reason: "DOWNTIME_ACTIVE",
  });
});

test("a controller disconnect pauses counting as a connectivity issue", () => {
  assert.deepEqual(getCountingDecision({ ...activeProduction, iotConnected: false }), {
    permitted: false,
    reason: "IOT_DISCONNECTED",
  });
});

test("inactive notifications pause counting even when BLE remains connected", () => {
  assert.deepEqual(getCountingDecision({ ...activeProduction, iotNotificationsActive: false }), {
    permitted: false,
    reason: "IOT_NOTIFICATIONS_INACTIVE",
  });
});

test("an invalid workstation view pauses counting", () => {
  assert.deepEqual(getCountingDecision({ ...activeProduction, workstationVisible: false }), {
    permitted: false,
    reason: "INVALID_WORKSTATION_VIEW",
  });
});

test("a session must be active before any count is permitted", () => {
  assert.deepEqual(getCountingDecision({ ...activeProduction, sessionActive: false }), {
    permitted: false,
    reason: "NO_ACTIVE_SESSION",
  });
});
