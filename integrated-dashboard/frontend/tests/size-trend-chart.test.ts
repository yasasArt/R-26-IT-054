import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sizeApp = readFileSync(path.join(frontendDirectory, "garment-size-frontend", "SizeApp.tsx"), "utf8");
const sizeStyles = readFileSync(path.join(frontendDirectory, "garment-size-frontend", "globals.css"), "utf8");

test("session output trend chart is fully labelled", () => {
  for (const label of [
    "Garments packed (pcs)",
    "Recent sessions (oldest &rarr; newest)",
    "Packed in session",
    "Session target",
    "Next-session forecast",
    "Session {index + 1}",
  ]) {
    assert.ok(sizeApp.includes(label), `missing label: ${label}`);
  }
  // A real scale with gridlines, and an accessible text summary of the bars.
  assert.match(sizeApp, /function niceScale\(/);
  assert.match(sizeApp, /role="img" aria-label=\{`Session output trend\./);
});

test("trend chart styles stay inside the size feature scope", () => {
  const scopeStart = sizeStyles.indexOf("@scope (.garment-size-module)");
  const scopeEnd = sizeStyles.indexOf("\n}\n", scopeStart);
  const trendRules = sizeStyles.indexOf(".trend-plot{");
  assert.ok(scopeStart >= 0 && scopeEnd > scopeStart);
  assert.ok(trendRules > scopeStart && trendRules < scopeEnd);
});
