import { afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";

// jsdom does not implement the AnimationEvent constructor. React-DOM feature-detects
// it at module load (react-dom-client.development.js) to decide whether to listen for
// the unprefixed "animationend" event or a vendor-prefixed fallback -- without this
// polyfill, onAnimationEnd handlers never fire in tests, even for a correctly
// dispatched "animationend" event. Must run before react-dom (and therefore
// @testing-library/react) is first imported, which is why the cleanup import below is
// deferred (dynamic import) rather than a static top-level import: a static import
// here would pull in react-dom during this file's own import phase -- before this
// polyfill's top-level statement runs -- since ES module imports always execute
// before other top-level code in the importing file, regardless of source order.
if (typeof window !== "undefined" && typeof window.AnimationEvent === "undefined") {
  window.AnimationEvent = window.Event as unknown as typeof AnimationEvent;
}

// vitest.config.mts does not set test.globals, so @testing-library/react's
// own auto-cleanup detection (which looks for a global `afterEach`) never
// fires -- without this, DOM from one test in a file leaks into the next.
afterEach(async () => {
  const { cleanup } = await import("@testing-library/react");
  cleanup();
});
