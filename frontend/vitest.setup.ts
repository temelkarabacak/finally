import "@testing-library/jest-dom/vitest";

// jsdom does not implement the AnimationEvent constructor. React-DOM feature-detects
// it at module load (react-dom-client.development.js) to decide whether to listen for
// the unprefixed "animationend" event or a vendor-prefixed fallback -- without this
// polyfill, onAnimationEnd handlers never fire in tests, even for a correctly
// dispatched "animationend" event. Must run before react-dom is first imported, hence
// living in a setup file rather than a test file.
if (typeof window !== "undefined" && typeof window.AnimationEvent === "undefined") {
  window.AnimationEvent = window.Event as unknown as typeof AnimationEvent;
}
