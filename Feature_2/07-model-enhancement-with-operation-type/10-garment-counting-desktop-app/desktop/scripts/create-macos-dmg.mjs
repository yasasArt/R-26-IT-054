import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const desktopDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const packageJson = JSON.parse(readFileSync(path.join(desktopDirectory, "package.json"), "utf8"));
const outputDirectory = path.join(desktopDirectory, "out");

function findApplication() {
  if (!existsSync(outputDirectory)) return null;

  for (const entry of readdirSync(outputDirectory, { withFileTypes: true })) {
    if (!entry.isDirectory() || !entry.name.includes("darwin")) continue;
    const candidate = path.join(outputDirectory, entry.name, `${packageJson.productName}.app`);
    if (existsSync(candidate)) return candidate;
  }

  return null;
}

if (process.platform !== "darwin") {
  console.error("A macOS DMG must be generated on macOS.");
  process.exitCode = 1;
} else {
  const application = findApplication();

  if (!application) {
    console.error("The packaged macOS application was not found. Run npm run release first.");
    process.exitCode = 1;
  } else {
    const installerDirectory = path.join(outputDirectory, "make", "dmg", process.arch);
    mkdirSync(installerDirectory, { recursive: true });
    const dmgFilename = path.join(
      installerDirectory,
      `Garment-Counter-${packageJson.version}-macOS-${process.arch}.dmg`,
    );
    const result = spawnSync(
      "hdiutil",
      ["create", "-volname", packageJson.productName, "-srcfolder", application, "-ov", "-format", "UDZO", dmgFilename],
      { stdio: "inherit" },
    );

    if (result.error || result.status !== 0) {
      console.error(`macOS DMG generation failed${result.error ? `: ${result.error.message}` : "."}`);
      process.exitCode = 1;
    } else {
      console.log(`macOS DMG created: ${dmgFilename}`);
    }
  }
}
