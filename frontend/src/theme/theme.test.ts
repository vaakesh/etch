import { describe, expect, it } from "vitest";
import { isAppTheme, resolveTheme } from "./theme";

describe("theme preferences", () => {
  it.each(["light", "dark", "system"])("accepts the %s backend value", (theme) => {
    expect(isAppTheme(theme)).toBe(true);
  });

  it("rejects unsupported backend theme values", () => {
    expect(isAppTheme("sepia")).toBe(false);
    expect(isAppTheme(null)).toBe(false);
  });

  it("resolves the system theme from the active media preference", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
  });
});
