import assert from "node:assert/strict";
import test from "node:test";

import { createPhaseOneReadiness } from "../src/shared/readiness.ts";

test("Phase 1 reports desktop readiness without pretending inference is operational", () => {
  const readiness = createPhaseOneReadiness(
    { classifierCheckpointExists: true, workstationCheckpointExists: true },
    "2026-08-21T10:00:00.000Z",
  );

  assert.equal(readiness.checkedAt, "2026-08-21T10:00:00.000Z");
  assert.equal(readiness.productionReady, false);
  assert.equal(readiness.completionPercent, 17);
  assert.equal(readiness.components.length, 6);
  assert.equal(readiness.components.find((component) => component.id === "desktop")?.status, "ready");
  assert.equal(
    readiness.components.find((component) => component.id === "workstation_detector")?.status,
    "attention",
  );
  assert.equal(
    readiness.components.find((component) => component.id === "garment_classifier")?.status,
    "attention",
  );
});

test("missing checkpoints are shown as blocked instead of being silently simulated", () => {
  const readiness = createPhaseOneReadiness({
    classifierCheckpointExists: false,
    workstationCheckpointExists: false,
  });

  assert.equal(
    readiness.components.find((component) => component.id === "workstation_detector")?.status,
    "blocked",
  );
  assert.equal(
    readiness.components.find((component) => component.id === "garment_classifier")?.status,
    "blocked",
  );
  assert.equal(readiness.productionReady, false);
});
