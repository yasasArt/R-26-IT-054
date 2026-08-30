import MiniCssExtractPlugin from "mini-css-extract-plugin";
import type { Configuration } from "webpack";

import { typeScriptRule } from "./webpack.main.config.ts";

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
        use: [MiniCssExtractPlugin.loader, "css-loader"],
      },
    ],
  },
  plugins: [
    new MiniCssExtractPlugin({
      filename: "[name].css",
    }),
  ],
  resolve: {
    extensions: [".js", ".ts", ".tsx", ".css", ".json"],
  },
};
