import javascript from "@eslint/js";
import globals from "globals";
import typescript from "typescript-eslint";

export default [
  {
    ignores: [".webpack/**", ".build-check/**", "out/**", "release/**", "coverage/**", "node_modules/**"],
  },
  javascript.configs.recommended,
  ...typescript.configs.recommended,
  {
    files: ["**/*.{ts,tsx,mjs}"],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
    },
  },
];
