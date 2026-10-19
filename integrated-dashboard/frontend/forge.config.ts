import type { ForgeConfig } from "@electron-forge/shared-types";
import { MakerSquirrel } from "@electron-forge/maker-squirrel";
import { MakerZIP } from "@electron-forge/maker-zip";
import { WebpackPlugin } from "@electron-forge/plugin-webpack";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import {
  missingReleaseBranding,
  missingReleaseModels,
  sidecarExecutableName,
  validateReleaseManifest,
  type ReleaseManifest,
} from "./src/shared/release-policy";
import { mainConfig } from "./webpack.main.config";
import { rendererConfig } from "./webpack.renderer.config";

const desktopDirectory = __dirname;
const modelDirectory = path.resolve(desktopDirectory, "..", "models");
const counterModelDirectory = path.join(modelDirectory, "garment-counter");
const brandingDirectory = path.resolve(desktopDirectory, "..", "resources", "branding");
const sidecarDirectory = path.join(desktopDirectory, "release", "sidecar");
const styleSidecarDirectory = path.join(desktopDirectory, "release", "style-colour-backend");
const featureSidecarDirectory = path.join(desktopDirectory, "release", "feature-sidecars");
const entitlementsPath = path.join(desktopDirectory, "packaging", "entitlements.mac.plist");
const macSigningIdentity = process.env.GARMENT_COUNTER_MAC_SIGNING_IDENTITY?.trim();
const appleId = process.env.GARMENT_COUNTER_APPLE_ID?.trim();
const applePassword = process.env.GARMENT_COUNTER_APPLE_APP_PASSWORD?.trim();
const appleTeamId = process.env.GARMENT_COUNTER_APPLE_TEAM_ID?.trim();

const config: ForgeConfig = {
  packagerConfig: {
    asar: true,
    appBundleId: "lk.zgen.garmentintelligence",
    executableName: "Garment Intelligence",
    icon: path.join(brandingDirectory, "icon"),
    extraResource: [modelDirectory, sidecarDirectory, styleSidecarDirectory, featureSidecarDirectory, brandingDirectory],
    ...(macSigningIdentity
      ? {
          osxSign: {
            identity: macSigningIdentity,
            optionsForFile: () => ({
              entitlements: entitlementsPath,
              hardenedRuntime: true,
            }),
          },
        }
      : {}),
    ...(macSigningIdentity && appleId && applePassword && appleTeamId
      ? {
          osxNotarize: {
            appleId,
            appleIdPassword: applePassword,
            teamId: appleTeamId,
          },
        }
      : {}),
    extendInfo: {
      LSApplicationCategoryType: "public.app-category.business",
      NSHighResolutionCapable: true,
      NSSupportsAutomaticGraphicsSwitching: true,
      NSCameraUsageDescription:
        "Garment Intelligence needs camera access for rework counting, sewing monitoring, style/colour detection, and garment sizing.",
      NSBluetoothAlwaysUsageDescription:
        "Garment Counter connects to the sewing operator's ESP32-C3 rework and downtime controller.",
      NSBluetoothPeripheralUsageDescription:
        "Garment Counter connects to the sewing operator's ESP32-C3 rework and downtime controller.",
    },
  },
  rebuildConfig: {},
  hooks: {
    prePackage: async (_forgeConfig, platform, architecture) => {
      const targetPlatform = (platform === "mas" ? "darwin" : platform) as NodeJS.Platform;
      const missingModels = missingReleaseModels(counterModelDirectory, path.join, existsSync);

      if (missingModels.length > 0) {
        throw new Error(`The release is missing trained model resources: ${missingModels.join(", ")}.`);
      }

      const featureModels = [
        path.join(modelDirectory, "garment-rework", "best.pt"),
        path.join(modelDirectory, "garment-style-colour", "best.pt"),
        path.join(modelDirectory, "garment-size", "best_model.pt"),
      ];
      if (featureModels.some((filename) => !existsSync(filename))) {
        throw new Error("The release is missing one or more rework, style/colour, or size-detection models.");
      }

      const missingBranding = missingReleaseBranding(brandingDirectory, path.join, existsSync);

      if (missingBranding.length > 0) {
        throw new Error(`The release is missing production application icons: ${missingBranding.join(", ")}.`);
      }

      const executable = path.join(sidecarDirectory, sidecarExecutableName(targetPlatform));
      const styleExecutable = path.join(
        styleSidecarDirectory,
        targetPlatform === "win32" ? "threadscan-backend.exe" : "threadscan-backend",
      );
      const reworkExecutable = path.join(featureSidecarDirectory, "rework", targetPlatform === "win32" ? "garment-rework-backend.exe" : "garment-rework-backend");
      const sizeExecutable = path.join(featureSidecarDirectory, "size", targetPlatform === "win32" ? "garment-size-backend.exe" : "garment-size-backend");
      const manifestFilename = path.join(sidecarDirectory, "release-manifest.json");

      if (!existsSync(executable) || !existsSync(manifestFilename)) {
        throw new Error(
          "The standalone Python application service has not been prepared. Run npm run release:prepare, then retry packaging.",
        );
      }

      if (!existsSync(styleExecutable)) {
        throw new Error(
          "The independent style/colour service has not been prepared. Run npm run release:prepare, then retry packaging.",
        );
      }
      if (!existsSync(reworkExecutable) || !existsSync(sizeExecutable)) {
        throw new Error("The rework and size feature services have not been prepared. Run npm run release:prepare, then retry packaging.");
      }

      const manifest = JSON.parse(readFileSync(manifestFilename, "utf8")) as ReleaseManifest;
      const releaseError = validateReleaseManifest(manifest, targetPlatform, architecture);

      if (releaseError) {
        throw new Error(releaseError);
      }
    },
  },
  makers: [
    new MakerSquirrel({
      name: "garment_intelligence",
      setupExe: "GarmentIntelligenceSetup.exe",
      setupIcon: path.join(brandingDirectory, "icon.ico"),
    }),
    new MakerZIP({}, ["darwin"]),
  ],
  plugins: [
    new WebpackPlugin({
      mainConfig,
      devContentSecurityPolicy: [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob: garmentstream: garmentrework: http://localhost:* http://127.0.0.1:*",
        "media-src 'self' blob: garmentstream: garmentrework:",
        "font-src 'self' data:",
        "connect-src 'self' http://localhost:* ws://localhost:* http://127.0.0.1:* ws://127.0.0.1:*",
      ].join("; "),
      renderer: {
        config: rendererConfig,
        entryPoints: [
          {
            name: "main_window",
            html: "./src/renderer/index.html",
            js: "./src/renderer/index.tsx",
            preload: {
              js: "./src/preload/preload.ts",
            },
          },
        ],
      },
    }),
  ],
};

export default config;
