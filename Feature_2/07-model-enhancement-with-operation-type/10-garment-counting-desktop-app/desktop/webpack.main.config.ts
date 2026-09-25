import type { Configuration, RuleSetRule } from "webpack";

const typeScriptRule: RuleSetRule = {
  test: /\.tsx?$/,
  exclude: /node_modules/,
  use: {
    loader: "ts-loader",
    options: {
      transpileOnly: true,
      compilerOptions: {
        noEmit: false,
        allowImportingTsExtensions: false,
      },
    },
  },
};

export const mainConfig: Configuration = {
  entry: "./src/main/main.ts",
  module: {
    rules: [typeScriptRule],
  },
  resolve: {
    extensions: [".js", ".ts", ".tsx", ".json"],
  },
};

export { typeScriptRule };
