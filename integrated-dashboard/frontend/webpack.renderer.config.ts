import MiniCssExtractPlugin from "mini-css-extract-plugin";
import path from "node:path";
import type { Configuration } from "webpack";

import { typeScriptRule } from "./webpack.main.config.ts";

const frontendDirectory = process.cwd();

export const rendererConfig: Configuration = {
  devtool: "source-map",
  performance: {
    maxAssetSize: 350_000,
    maxEntrypointSize: 350_000,
  },
  module: {
    rules: [
      typeScriptRule,
      {
        test: /\.css$/i,
        oneOf: [
          {
            include: [
              path.resolve(frontendDirectory, "garment-style-colour-frontend"),
              path.resolve(frontendDirectory, "garment-rework-frontend"),
              path.resolve(frontendDirectory, "garment-size-frontend"),
            ],
            use: [
              MiniCssExtractPlugin.loader,
              "css-loader",
              {
                loader: "postcss-loader",
                options: {
                  postcssOptions: {
                    plugins: ["@tailwindcss/postcss"],
                  },
                },
              },
            ],
          },
          { use: [MiniCssExtractPlugin.loader, "css-loader"] },
        ],
      },
    ],
  },
  plugins: [
    new MiniCssExtractPlugin({
      filename: "[name].css",
    }),
  ],
  resolve: {
    alias: {
      "@platform": path.resolve(frontendDirectory, "src"),
      "@garment-counter": path.resolve(frontendDirectory, "garment-counter-frontend"),
      "@garment-rework": path.resolve(frontendDirectory, "garment-rework-frontend"),
      "@garment-style-colour": path.resolve(frontendDirectory, "garment-style-colour-frontend"),
      "@garment-size": path.resolve(frontendDirectory, "garment-size-frontend"),
    },
    extensions: [".js", ".jsx", ".ts", ".tsx", ".css", ".json"],
  },
};
