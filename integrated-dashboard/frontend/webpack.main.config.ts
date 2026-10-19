import type { Configuration, RuleSetRule } from "webpack";

const typeScriptRule: RuleSetRule = {
  test: /\.[jt]sx?$/,
  exclude: /node_modules/,
  use: {
    loader: "ts-loader",
    options: {
      transpileOnly: true,
      compilerOptions: {
        noEmit: false,
        allowImportingTsExtensions: false,
        allowJs: true,
        checkJs: false,
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
