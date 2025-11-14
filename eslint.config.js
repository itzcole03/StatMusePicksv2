import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import testingLibrary from "eslint-plugin-testing-library";
import vitestPlugin from "eslint-plugin-vitest";

// Configure ESLint for JS and TS. Use @typescript-eslint directly instead of
// the `typescript-eslint` helper package to avoid runtime mismatches between
// plugin and helper wrappers.
export default [
  js.configs.recommended,
  // Global ignores are required for CLI runs when using the flat config format
  {
    ignores: [
      ".venv",
      "backend/.venv",
      "dist",
      "node_modules",
      "coverage",
      "logs",
      "*.lock",
      "package-lock.json",
      "npm-debug.log",
      "yarn-error.log",
    ],
  },
  {
    ignores: [
      "node_modules",
      "dist",
      ".venv",
      "backend/.venv",
      "logs",
      "**/*.min.js",
      "coverage",
      "*.lock",
      "package-lock.json",
    ],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2020,
        sourceType: "module",
        // Omit `project` for broad lint runs to avoid typed-linting errors on test/config files.
        // If you want type-aware rules, add a dedicated override with a project pointing to a tsconfig that includes only the sources.
      },
      globals: globals.browser,
    },
    
    plugins: {
      "@typescript-eslint": tsPlugin,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // Keep this rule off for now; enable progressively after tuning config
      "@typescript-eslint/no-unused-expressions": "off",
      // Allow unused variables/args that start with `_` (e.g. `_e`, `_err`) or common placeholder names (e, err)
      "no-unused-vars": ["warn", { "argsIgnorePattern": "^(_.*|e|err)$", "varsIgnorePattern": "^(_.*|e|err)$" }],
      "@typescript-eslint/no-unused-vars": ["warn", { "argsIgnorePattern": "^(_.*|e|err)$", "varsIgnorePattern": "^(_.*|e|err)$" }],
      // Allow empty catch blocks (we prefer explicit no-op comments in code where appropriate)
      "no-empty": ["error", { "allowEmptyCatch": true }],
    },
  },
  // Typed linting for application source files only
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        project: ["./tsconfig.eslint.json"]
      },
      globals: globals.browser,
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
    },
  },
  // Test files: enable Jest globals and Node env
  {
    files: ["**/__tests__/**", "**/*.test.{ts,tsx}", "src/**/*.test.{ts,tsx}", "**/tests/**", "src/tests/**", "**/*.spec.{ts,tsx}", "vitest.setup.ts"],
    languageOptions: {
      globals: { ...globals.jest, ...globals.node, vi: true, describe: true, it: true, expect: true, beforeEach: true, afterEach: true },
    },
    plugins: {
      "vitest": vitestPlugin,
      "testing-library": testingLibrary,
    },
    rules: {
      ...(testingLibrary.configs && testingLibrary.configs.recommended && testingLibrary.configs.recommended.rules ? testingLibrary.configs.recommended.rules : {}),
      ...(vitestPlugin.configs && vitestPlugin.configs.recommended && vitestPlugin.configs.recommended.rules ? vitestPlugin.configs.recommended.rules : {}),
    },
  },
  // Scripts and tooling: enable Node globals for scripts and CLI helpers
  {
    files: ["scripts/**/*.{js,cjs,mjs,ts}", "scripts/**", "*.cjs", "*.mjs"],
    languageOptions: {
      globals: globals.node,
      parserOptions: {
        sourceType: "script",
      },
    },
  },
  // Playwright smoke script: runs in browser contexts and uses browser globals
  {
    files: ["scripts/playwright_smoke.mjs", "scripts/playwright_smoke.*"],
    languageOptions: {
      globals: { ...globals.browser, indexedDB: true, performance: true },
      parserOptions: {
        sourceType: "module",
      },
    },
  },
];
