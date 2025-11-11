import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";

// Configure ESLint for JS and TS. Use @typescript-eslint directly instead of
// the `typescript-eslint` helper package to avoid runtime mismatches between
// plugin and helper wrappers.
export default [
  js.configs.recommended,
  {
    ignores: ["dist", ".venv", "backend/.venv"],
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
    files: ["**/__tests__/**", "**/*.test.{ts,tsx}", "src/**/*.test.{ts,tsx}"],
    languageOptions: {
      globals: { ...globals.jest, ...globals.node },
    },
  },
];
