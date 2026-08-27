import react from "@vitejs/plugin-react";
// `vitest/config` re-exports Vite's `defineConfig` with the `test` key typed
// in. Importing from `vite` instead type-checks fine at first glance, but
// `tsc` then rejects the `test` block below as an unknown property.
import { defineConfig } from "vitest/config";

// `base` must match PASS_DESIGNER_ROOT_PATH. They come from one variable in
// the deployment; if they drift, the SPA fetches its own assets from the root
// and serves a white page.
export default defineConfig({
  base: process.env.PASS_DESIGNER_ROOT_PATH || "/",
  plugins: [react()],
  build: { outDir: "../src/edutap/pass_designer/web/static", emptyOutDir: true },
  test: { environment: "jsdom", globals: true, setupFiles: "./src/setup-tests.ts" },
});
