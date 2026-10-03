import { describe, expect, it } from "vitest";
import { getPopoverPosition } from "./popover-position";

const viewport = { left: 0, top: 0, width: 375, height: 667 };

describe("getPopoverPosition", () => {
  it("opens a compact menu next to a trigger near the top of a phone", () => {
    expect(getPopoverPosition({ right: 351, top: 100, bottom: 144 }, 160, viewport)).toEqual({
      left: 135,
      top: 152,
      width: 216,
      maxHeight: 503,
      origin: "top right",
    });
  });

  it("opens above a bottom-row trigger instead of falling off the screen", () => {
    expect(getPopoverPosition({ right: 351, top: 595, bottom: 639 }, 160, viewport)).toMatchObject({
      left: 135,
      top: 427,
      origin: "bottom right",
    });
  });

  it("uses the visible viewport when the keyboard reduces the available height", () => {
    expect(
      getPopoverPosition({ right: 351, top: 220, bottom: 264 }, 160, {
        ...viewport,
        height: 300,
      }),
    ).toMatchObject({ top: 52, origin: "bottom right" });
  });

  it("allows internal scrolling when neither side fits the whole menu", () => {
    expect(
      getPopoverPosition({ right: 351, top: 110, bottom: 154 }, 160, {
        ...viewport,
        height: 260,
      }),
    ).toMatchObject({ top: 12, maxHeight: 90, origin: "bottom right" });
  });

  it("keeps the menu inside a zoomed and shifted visual viewport", () => {
    expect(
      getPopoverPosition({ right: 278, top: 340, bottom: 384 }, 160, {
        left: 50,
        top: 120,
        width: 240,
        height: 320,
      }),
    ).toMatchObject({ left: 62, top: 172, width: 216, origin: "bottom right" });
  });

  it.each([320, 375, 390, 430, 600])("keeps a menu compact on a %ipx screen", (width) => {
    const position = getPopoverPosition({ right: width - 24, top: 100, bottom: 144 }, 160, {
      ...viewport,
      width,
    });
    expect(position.width).toBe(216);
    expect(position.left).toBeGreaterThanOrEqual(12);
    expect(position.left + position.width).toBeLessThanOrEqual(width - 12);
  });
});
