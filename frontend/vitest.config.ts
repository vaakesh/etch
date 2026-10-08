import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    clearMocks: true,
    exclude: [...configDefaults.exclude, "e2e/**"],
    environment: "node",
    restoreMocks: true,
  },
});
