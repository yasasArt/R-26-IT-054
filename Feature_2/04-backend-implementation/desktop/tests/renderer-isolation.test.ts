import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

test("preload and renderer contain no backend credential or direct request header", async () => {
  const preload = await readFile("src/preload/index.ts", "utf8");
  const renderer = await readFile("src/renderer/services/api.ts", "utf8");
  const exposed = `${preload}\n${renderer}`;

  assert.doesNotMatch(exposed, /GARMENT_COUNTER_API_TOKEN/);
  assert.doesNotMatch(exposed, /Authorization/);
  assert.doesNotMatch(exposed, /Bearer\s/);
  assert.doesNotMatch(renderer, /\bfetch\s*\(/);
  assert.doesNotMatch(preload, /exposeInMainWorld\([^,]+,\s*ipcRenderer/);
});

