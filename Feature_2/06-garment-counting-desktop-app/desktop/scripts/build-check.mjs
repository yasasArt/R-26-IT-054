import path from "node:path";

import webpack from "webpack";

import { mainConfig } from "../webpack.main.config.ts";
import { rendererConfig } from "../webpack.renderer.config.ts";

const buildDirectory = path.resolve(".build-check");

const configurations = [
  {
    ...mainConfig,
    name: "electron-main",
    mode: "production",
    target: "electron-main",
    output: {
      path: path.join(buildDirectory, "main"),
      filename: "main.js",
    },
  },
  {
    ...mainConfig,
    name: "electron-preload",
    mode: "production",
    target: "electron-preload",
    entry: "./src/preload/preload.ts",
    output: {
      path: path.join(buildDirectory, "preload"),
      filename: "preload.js",
    },
  },
  {
    ...rendererConfig,
    name: "react-renderer",
    mode: "production",
    target: "web",
    entry: "./src/renderer/index.tsx",
    output: {
      path: path.join(buildDirectory, "renderer"),
      filename: "renderer.js",
    },
  },
];

webpack(configurations, (error, statistics) => {
  if (error) {
    console.error(error);
    process.exitCode = 1;
    return;
  }

  if (!statistics) {
    console.error("Webpack completed without producing build statistics.");
    process.exitCode = 1;
    return;
  }

  console.info(
    statistics.toString({
      colors: true,
      assets: true,
      chunks: false,
      modules: false,
      children: true,
      warnings: true,
      errors: true,
      errorDetails: true,
    }),
  );

  if (statistics.hasErrors()) {
    process.exitCode = 1;
  }
});
