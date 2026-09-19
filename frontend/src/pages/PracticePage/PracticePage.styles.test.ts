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

  it("keeps the active card geometry fixed while fitting the prompt inside it", () => {
    const stageDeclarations = practicePageStyles.match(/\.cardStage\s*\{([^}]*)\}/)?.[1];
    const cardDeclarations = practicePageStyles.match(/\.practiceCard\s*\{([^}]*)\}/)?.[1];
    const promptDeclarations = practicePageStyles.match(/\.promptArea\s*\{([^}]*)\}/)?.[1];
    const answerDeclarations = practicePageStyles.match(/\.answerRegion\s*\{([^}]*)\}/)?.[1];

    expect(stageDeclarations).toContain("width: min(100%, 1078px);");
    expect(cardDeclarations).toContain("height: clamp(484px, 68.2vh, 704px);");
    expect(cardDeclarations).toContain("grid-template-rows: auto minmax(0, 1fr) auto;");
    expect(promptDeclarations).toContain("overflow: hidden;");
    expect(answerDeclarations).toContain("height: 172px;");
  });
});

describe("practice history card presentation", () => {
  it("uses one smoothly moving indicator for the active history filter", () => {
    const filterDeclarations = practicePageStyles.match(/\.historyFilters\s*\{([^}]*)\}/)?.[1];
    const indicatorDeclarations = practicePageStyles.match(
      /\.historyFilterIndicator\s*\{([^}]*)\}/,
    )?.[1];

    expect(filterDeclarations).toContain("position: relative;");
    expect(indicatorDeclarations).toContain("pointer-events: none;");
    expect(indicatorDeclarations).toContain("transform: translate3d(");
    expect(indicatorDeclarations).toContain("transform 260ms cubic-bezier(0.22, 1, 0.36, 1);");
    expect(practicePageStyles).toContain(
      '.historyFilters[data-indicator-ready="true"] .historyFilterIndicator',
    );
  });

  it("keeps session cards static and uses a plain outline", () => {
    const declarations = practicePageStyles.match(/\.historyCard\s*\{([^}]*)\}/)?.[1];

    expect(declarations).toContain("border: 1px solid var(--history-card-line);");
    expect(declarations).not.toContain("animation:");
    expect(declarations).not.toContain("box-shadow:");
    expect(declarations).not.toContain("transform:");
    expect(practicePageStyles).not.toContain(".historyCard::before");
    expect(practicePageStyles).not.toContain(".historyCard:hover");
  });

  it("gives repeat and history actions the secondary accent", () => {
    const declarations = practicePageStyles.match(
      /\.historyDetailsButton,\s*\.historyRepeatButton\s*\{([^}]*)\}/,
    )?.[1];

    expect(declarations).toContain("color: var(--history-secondary);");
    expect(declarations).toContain("background: var(--history-secondary-surface);");
    expect(declarations).toContain("border: 1px solid var(--history-secondary-line);");
  });
});
