import { describe, expect, it, vi } from "vitest";
import { completeInitialBoot } from "./initial-boot";

describe("completeInitialBoot", () => {
  it("reveals the React root and removes the HTML loader", () => {
    const rootElement = { removeAttribute: vi.fn() };
    const bootLoaderElement = { remove: vi.fn() };

    completeInitialBoot(rootElement, bootLoaderElement);

    expect(rootElement.removeAttribute.mock.calls).toEqual([
      ["data-booting"],
      ["aria-hidden"],
      ["inert"],
    ]);
    expect(bootLoaderElement.remove).toHaveBeenCalledOnce();
  });

  it("keeps the HTML loader when the React root is unavailable", () => {
    const bootLoaderElement = { remove: vi.fn() };

    completeInitialBoot(null, bootLoaderElement);

    expect(bootLoaderElement.remove).not.toHaveBeenCalled();
  });
});
