import { defineConfig } from "vitest/config";

export default defineConfig({
  base: "./", // relative asset paths, so dist/ works on GitHub Pages or any sub-path
  test: {
    environment: "node", // core tests are pure; no DOM or WebGL needed
    include: ["tests/**/*.test.ts"],
  },
});
