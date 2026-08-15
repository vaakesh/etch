/// <reference types="node" />

import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const practicePageStyles = readFileSync(
  new URL("./PracticePage.module.css", import.meta.url),
  "utf8",
);

describe("practice card text wrapping", () => {
  it.each([".promptArea h1", ".feedbackAnswer"])(
    "keeps words intact in %s when they fit on a line",
    (selector) => {
      const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const declarations = practicePageStyles.match(
        new RegExp(`${escapedSelector}\\s*\\{([^}]*)\\}`),
      )?.[1];

      expect(declarations).toContain("overflow-wrap: break-word;");
      expect(declarations).toContain("word-break: normal;");
      expect(declarations).not.toContain("overflow-wrap: anywhere;");
    },
  );
});
