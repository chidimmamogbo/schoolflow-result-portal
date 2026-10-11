// Vitest settings for frontend unit and component tests.
// Setup follows the official Next.js 16.4 guide (docs/01-app/02-guides/testing/vitest.mdx),
// except `@/` imports use Vite's built-in resolve.tsconfigPaths instead of the
// vite-tsconfig-paths plugin (Vite 8 supports it natively).
// Run with `bun run test`, never `bun test` (that is Bun's own test runner, D-108).
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    tsconfigPaths: true,
  },
  test: {
    // jsdom is a fake browser page, so components can render without a real browser.
    environment: "jsdom",
  },
});
