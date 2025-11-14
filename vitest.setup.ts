import "@testing-library/jest-dom";

// Vitest setup: registers jest-dom matchers for DOM assertions
// Register a Node-friendly IndexedDB implementation for tests that need it.
// `fake-indexeddb/auto` instantiates global `indexedDB` and related APIs.
try {
	require("fake-indexeddb/auto");
} catch {
	// Ignore if the package isn't installed in the current environment.
}

// Register centralized test mocks so component tests don't need to import mocks manually.
try {
	require('./src/tests/testUtils/mockServices');
} catch {
	// If the helper isn't present, tests will still work because some tests
	// import mocks directly; swallow the error to avoid failing setup.
}
