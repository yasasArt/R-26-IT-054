import assert from "node:assert/strict";
import test from "node:test";

import {
  getResearchComponentCount,
  getWorkstation,
  WORKSTATION_MODULES,
} from "../src/renderer/modules/platform/module-registry.ts";

test("the shared platform exposes four features in production-flow order", () => {
  assert.deepEqual(WORKSTATION_MODULES.map((workstation) => workstation.id), ["sewing", "rework", "style-colour", "size"]);
  assert.equal(new Set(WORKSTATION_MODULES.map((workstation) => workstation.backendDirectory)).size, 4);
});

test("the four cards represent all four research components", () => {
  assert.equal(getResearchComponentCount(), 4);
  assert.equal(getWorkstation("rework").componentCount, 1);
  assert.equal(getWorkstation("sewing").componentCount, 1);
  assert.equal(getWorkstation("style-colour").componentCount, 1);
  assert.equal(getWorkstation("size").componentCount, 1);
});

test("all supplied research components are available", () => {
  assert.equal(getWorkstation("rework").availability, "available");
  assert.equal(getWorkstation("sewing").availability, "available");
  assert.equal(getWorkstation("style-colour").availability, "available");
  assert.equal(getWorkstation("size").availability, "available");
});

test("each research feature retains separate frontend, backend, and trained-model ownership", () => {
  assert.equal(
    getWorkstation("sewing").frontendEntry,
    "frontend/garment-counter-frontend/SewingWorkspace.tsx",
  );
  assert.equal(getWorkstation("sewing").backendDirectory, "backend/garment-counter-backend/");
  assert.equal(getWorkstation("sewing").modelDirectory, "models/garment-counter/");

  assert.equal(getWorkstation("rework").backendDirectory, "backend/garment-rework-backend/");
  assert.equal(getWorkstation("style-colour").backendDirectory, "backend/garment-style-colour-backend/");
  assert.equal(getWorkstation("size").backendDirectory, "backend/garment-size-backend/");

  assert.equal(getWorkstation("rework").modelDirectory, "models/garment-rework/");
  assert.equal(getWorkstation("style-colour").modelDirectory, "models/garment-style-colour/");
  assert.equal(getWorkstation("size").modelDirectory, "models/garment-size/");
});
