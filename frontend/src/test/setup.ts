// Shared test setup, imported at the top of each test file: the fake API (MSW),
// a fake router, the browser features jsdom lacks, and cleanup between tests.
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, vi } from "vitest";

export const server = setupServer();

// Typing into forms one key at a time is slow on a busy laptop.
vi.setConfig({ testTimeout: 30_000 });

export const router = {
  push: vi.fn(),
  replace: vi.fn(),
  back: vi.fn(),
  refresh: vi.fn(),
  prefetch: vi.fn(),
};

export const navigation = {
  pathname: "/",
  params: {} as Record<string, string>,
  search: new URLSearchParams(),
};

// next/font downloads fonts while building; tests only need the class name.
vi.mock("next/font/google", () => ({
  Inter: () => ({ variable: "font-inter", className: "font-inter" }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => router,
  usePathname: () => navigation.pathname,
  useParams: () => navigation.params,
  useSearchParams: () => navigation.search,
}));

beforeAll(() => {
  server.listen({ onUnhandledFrame: "error" });
  // jsdom has no matchMedia; next-themes asks it for the system theme.
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
  // Radix menus and tooltips measure the page with ResizeObserver.
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

afterEach(() => {
  cleanup();
  server.resetHandlers();
  vi.clearAllMocks();
  navigation.pathname = "/";
  navigation.params = {};
  navigation.search = new URLSearchParams();
  window.localStorage.clear();
});

afterAll(() => server.close());
