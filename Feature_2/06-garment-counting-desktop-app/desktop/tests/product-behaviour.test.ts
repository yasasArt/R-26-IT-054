import assert from "node:assert/strict";
import test from "node:test";

import {
  CLASSIFIER_STATES,
  COUNT_TRANSITION,
  hasExpectedClassifierStates,
  hasExpectedWorkstationClass,
  OPERATOR_MODES,
  PHYSICAL_RESET_ACTION,
  WORKSTATION_CLASS,
} from "../src/shared/product-behaviour.ts";

test("the sewing classifier exposes exactly the two trained classes", () => {
  assert.deepEqual(CLASSIFIER_STATES, ["IDLE_SETUP", "SEWING"]);
  assert.equal(hasExpectedClassifierStates(["IDLE_SETUP", "SEWING"]), true);
  assert.equal(hasExpectedClassifierStates(["SEWING", "IDLE_SETUP"]), false);
  assert.equal(hasExpectedClassifierStates(["IDLE_SETUP", "SEWING", "FOLDING"]), false);
});

test("a completed garment is the confirmed sewing-to-idle transition", () => {
  assert.deepEqual(COUNT_TRANSITION, { from: "SEWING", to: "IDLE_SETUP" });
});

test("the workstation detector validates one generic workstation class", () => {
  assert.equal(WORKSTATION_CLASS, "workstation");
  assert.equal(hasExpectedWorkstationClass(["workstation"]), true);
  assert.equal(hasExpectedWorkstationClass(["workstation", "person"]), false);
  assert.equal(hasExpectedWorkstationClass(["workstation-01"]), false);
});

test("the three operator modes are explicit and mutually exclusive", () => {
  assert.deepEqual(OPERATOR_MODES, ["NORMAL", "REWORK", "DOWNTIME"]);
});

test("the physical reset button returns to normal and never resets production counts", () => {
  assert.equal(PHYSICAL_RESET_ACTION, "RETURN_TO_NORMAL");
});
