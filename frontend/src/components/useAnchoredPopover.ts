import { useCallback, useEffect, useRef, type MouseEvent } from "react";
import { getPopoverPosition } from "./popover-position";

export function useAnchoredPopover() {
  const menuRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const positionMenu = useCallback(() => {
    const menu = menuRef.current;
    const trigger = triggerRef.current;
    if (menu === null || trigger === null || !menu.matches(":popover-open")) {
      return;
    }

    const visualViewport = window.visualViewport;
    const viewport = {
      left: visualViewport?.offsetLeft ?? 0,
      top: visualViewport?.offsetTop ?? 0,
      width: visualViewport?.width ?? window.innerWidth,
      height: visualViewport?.height ?? window.innerHeight,
    };
    const triggerRect = trigger.getBoundingClientRect();
    if (
      triggerRect.bottom <= viewport.top ||
      triggerRect.top >= viewport.top + viewport.height ||
      triggerRect.right <= viewport.left ||
      triggerRect.left >= viewport.left + viewport.width
    ) {
      menu.hidePopover();
      return;
    }

    menu.style.setProperty(
      "--card-actions-menu-width",
      `${Math.max(0, Math.min(216, viewport.width - 24))}px`,
    );
    menu.style.setProperty(
      "--card-actions-menu-max-height",
      `${Math.max(0, viewport.height - 24)}px`,
    );
    const position = getPopoverPosition(triggerRect, menu.offsetHeight, viewport);
    menu.style.setProperty("--card-actions-menu-left", `${position.left}px`);
    menu.style.setProperty("--card-actions-menu-top", `${position.top}px`);
    menu.style.setProperty("--card-actions-menu-max-height", `${position.maxHeight}px`);
    menu.style.setProperty("--card-actions-menu-origin", position.origin);
  }, []);

  useEffect(() => {
    const viewport = window.visualViewport;
    function handleScroll(event: Event): void {
      if (event.target instanceof Node && menuRef.current?.contains(event.target)) {
        return;
      }
      positionMenu();
    }

    window.addEventListener("resize", positionMenu);
    document.addEventListener("scroll", handleScroll, true);
    viewport?.addEventListener("resize", positionMenu);
    viewport?.addEventListener("scroll", positionMenu);
    return () => {
      window.removeEventListener("resize", positionMenu);
      document.removeEventListener("scroll", handleScroll, true);
      viewport?.removeEventListener("resize", positionMenu);
      viewport?.removeEventListener("scroll", positionMenu);
    };
  }, [positionMenu]);

  function toggleMenu(event: MouseEvent<HTMLButtonElement>): void {
    event.preventDefault();
    const menu = menuRef.current;
    const trigger = triggerRef.current;
    if (menu === null || trigger === null) {
      return;
    }
    if (menu.matches(":popover-open")) {
      menu.hidePopover();
      return;
    }

    menu.style.visibility = "hidden";
    try {
      menu.showPopover({ source: trigger });
      positionMenu();
    } finally {
      menu.style.removeProperty("visibility");
    }
  }

  return { menuRef, triggerRef, toggleMenu };
}
