import "@testing-library/jest-dom";

// Vitest setup: registers jest-dom matchers for DOM assertions
// Register a Node-friendly IndexedDB implementation for tests that need it.
// `fake-indexeddb/auto` instantiates global `indexedDB` and related APIs.
try {
	// eslint-disable-next-line @typescript-eslint/no-var-requires
	require("fake-indexeddb/auto");
} catch (e) {
	// Ignore if the package isn't installed in the current environment.
}
