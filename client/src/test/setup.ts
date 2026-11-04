import "@testing-library/jest-dom/vitest";

type MediaQueryStub = Pick<
  MediaQueryList,
  "matches" | "media" | "addEventListener" | "removeEventListener"
>;

// jsdom has no matchMedia; tests render the desktop layout.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string): MediaQueryStub => ({
    matches: true,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }),
});

// jsdom has no ResizeObserver; layout never changes there, so observing can be a no-op.
class ResizeObserverStub {
  observe = (): undefined => undefined;
  unobserve = (): undefined => undefined;
  disconnect = (): undefined => undefined;
}
Object.defineProperty(window, "ResizeObserver", {
  writable: true,
  value: ResizeObserverStub,
});
