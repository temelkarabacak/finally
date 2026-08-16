import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

/** jsdom ships no EventSource; the terminal opens one on mount. */
class StubEventSource {
  static readonly CLOSED = 2;
  readonly CLOSED = 2;
  readyState = 1;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  close = vi.fn();
}

vi.stubGlobal("EventSource", StubEventSource);

/** Recharts measures its container, which jsdom always reports as 0x0. */
Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 640 });
Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 360 });
vi.stubGlobal(
  "ResizeObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
);

afterEach(cleanup);
