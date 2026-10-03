interface PopoverViewport {
  left: number;
  top: number;
  width: number;
  height: number;
}

interface PopoverTrigger {
  right: number;
  top: number;
  bottom: number;
}

export function getPopoverPosition(
  trigger: PopoverTrigger,
  menuHeight: number,
  viewport: PopoverViewport,
) {
  const padding = 12;
  const gap = 8;
  const width = Math.max(0, Math.min(216, viewport.width - padding * 2));
  const left = Math.max(
    viewport.left + padding,
    Math.min(trigger.right - width, viewport.left + viewport.width - width - padding),
  );
  const spaceBelow = Math.max(0, viewport.top + viewport.height - padding - trigger.bottom - gap);
  const spaceAbove = Math.max(0, trigger.top - gap - viewport.top - padding);
  const opensBelow =
    menuHeight <= spaceBelow || (menuHeight > spaceAbove && spaceBelow >= spaceAbove);
  const maxHeight = opensBelow ? spaceBelow : spaceAbove;
  const height = Math.min(menuHeight, maxHeight);
  const top = Math.max(
    viewport.top + padding,
    Math.min(
      opensBelow ? trigger.bottom + gap : trigger.top - gap - height,
      viewport.top + viewport.height - padding - height,
    ),
  );

  return { left, top, width, maxHeight, origin: opensBelow ? "top right" : "bottom right" };
}
