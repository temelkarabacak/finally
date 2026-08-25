import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// vitest.config.mts does not set test.globals, so @testing-library/react's
// own auto-cleanup detection (which looks for a global `afterEach`) never
// fires -- without this, DOM from one test in a file leaks into the next.
afterEach(() => {
  cleanup();
});
