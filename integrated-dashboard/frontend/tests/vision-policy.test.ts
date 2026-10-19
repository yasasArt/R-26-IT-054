import assert from "node:assert/strict";
import test from "node:test";

import { allowsRecordedWorkstationVideo, describeSewingActivity } from "../src/shared/vision-policy.ts";

test("operators see direct, understandable sewing-state descriptions", () => {
  assert.equal(
    describeSewingActivity({ running: true, phase: "MONITORING", sewing_state: "SEWING" }),
    "Sewing in progress",
  );
  assert.equal(
    describeSewingActivity({ running: true, phase: "MONITORING", sewing_state: "IDLE_SETUP" }),
    "Ready for next garment",
  );
});

test("unsafe or unavailable workstation states are never described as active counting", () => {
  assert.equal(describeSewingActivity(null), "Monitoring not started");
  assert.equal(
    describeSewingActivity({ running: true, phase: "PAUSED", sewing_state: "SEWING" }),
    "Counting paused",
  );
  assert.equal(
    describeSewingActivity({ running: true, phase: "MONITORING", sewing_state: "INVALID_VIEW" }),
    "Workstation not visible",
  );
});

test("recorded test workflows are available in validation and production sessions", () => {
  assert.equal(allowsRecordedWorkstationVideo("VALIDATION"), true);
  assert.equal(allowsRecordedWorkstationVideo("PRODUCTION"), true);
});
