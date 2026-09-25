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
const modelDirectory = path.resolve(desktopDirectory, "..", "resources", "models");
const brandingDirectory = path.resolve(desktopDirectory, "..", "resources", "branding");
const sidecarDirectory = path.join(desktopDirectory, "release", "sidecar");
const entitlementsPath = path.join(desktopDirectory, "packaging", "entitlements.mac.plist");
const macSigningIdentity = process.env.GARMENT_COUNTER_MAC_SIGNING_IDENTITY?.trim();
const appleId = process.env.GARMENT_COUNTER_APPLE_ID?.trim();
const applePassword = process.env.GARMENT_COUNTER_APPLE_APP_PASSWORD?.trim();
const appleTeamId = process.env.GARMENT_COUNTER_APPLE_TEAM_ID?.trim();

const config: ForgeConfig = {
  packagerConfig: {
    asar: true,
    appBundleId: "lk.zgen.garmentcounter",
    executableName: "Garment Counter",
    icon: path.join(brandingDirectory, "icon"),
    extraResource: [modelDirectory, sidecarDirectory, brandingDirectory],
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
        "Garment Counter needs camera access to verify and monitor the configured sewing workstation.",
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
      const missingModels = missingReleaseModels(modelDirectory, path.join, existsSync);

      if (missingModels.length > 0) {
        throw new Error(`The release is missing trained model resources: ${missingModels.join(", ")}.`);
      }

      const missingBranding = missingReleaseBranding(brandingDirectory, path.join, existsSync);

      if (missingBranding.length > 0) {
        throw new Error(`The release is missing production application icons: ${missingBranding.join(", ")}.`);
      }

      const executable = path.join(sidecarDirectory, sidecarExecutableName(targetPlatform));
      const manifestFilename = path.join(sidecarDirectory, "release-manifest.json");

      if (!existsSync(executable) || !existsSync(manifestFilename)) {
        throw new Error(
          "The standalone Python application service has not been prepared. Run npm run release:prepare, then retry packaging.",
        );
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
      name: "garment_counter",
      setupExe: "GarmentCounterSetup.exe",
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
        "img-src 'self' data: blob: garmentstream:",
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
