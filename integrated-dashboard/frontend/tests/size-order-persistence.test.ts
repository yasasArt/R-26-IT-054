import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectDirectory = path.resolve(frontendDirectory, "..");
const sizeApp = readFileSync(
  path.join(frontendDirectory, "garment-size-frontend", "SizeApp.tsx"),
  "utf8",
);
const desktopIpc = readFileSync(
  path.join(frontendDirectory, "src", "main", "ipc.ts"),
  "utf8",
);
const sizeDatabase = readFileSync(
  path.join(projectDirectory, "backend", "garment-size-backend", "database.py"),
  "utf8",
);
const sizeBackend = readFileSync(
  path.join(projectDirectory, "backend", "garment-size-backend", "main.py"),
  "utf8",
);

test("new size orders start from a fresh form and a fresh backend count session", () => {
  assert.match(sizeApp, /function createInitialSchedule\(\)/);
  assert.match(sizeApp, /"POST",\s*"\/counts\/reset"/);
  assert.match(sizeApp, /baselineCounts:\s*freshCounts/);
  assert.doesNotMatch(sizeApp, /localStorage\.setItem\(STORE\.sessions/);
});

test("order dates are validated in both the renderer and backend", () => {
  assert.match(sizeApp, /draft\.startDate > draft\.endDate/);
  assert.match(sizeApp, /End date cannot be before start date/);
  assert.match(sizeBackend, /datetime\.strptime\(value, "%Y-%m-%d"\)/);
  assert.match(sizeBackend, /if start_date > end_date:/);
});

test("order history uses an allow-listed SQLite CRUD path including individual delete", () => {
  assert.match(desktopIpc, /"\/orders"/);
  assert.match(desktopIpc, /method === "DELETE"/);
  assert.match(sizeDatabase, /CREATE TABLE IF NOT EXISTS production_orders/);
  assert.match(sizeDatabase, /def delete_production_order\(session_id: str\)/);
  assert.match(sizeBackend, /@app\.delete\("\/orders\/\{session_id\}"\)/);
  assert.match(sizeApp, /Delete \$\{session\.orderId\} permanently from the database/);
});
