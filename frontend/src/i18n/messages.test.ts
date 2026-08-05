import { describe, expect, it } from "vitest";
import { defineMessages } from "./messages";

describe("localized messages", () => {
  it("keeps both supported locales under the same typed shape", () => {
    const messages = defineMessages(
      { title: "Настройки", greeting: (name: string) => `Привет, ${name}` },
      { title: "Settings", greeting: (name: string) => `Hello, ${name}` },
    );

    expect(messages["ru-RU"].greeting("Alice")).toBe("Привет, Alice");
    expect(messages["en-US"].greeting("Alice")).toBe("Hello, Alice");
  });
});
