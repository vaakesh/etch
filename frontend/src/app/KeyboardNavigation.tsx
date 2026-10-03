import { useEffect } from "react";

const NAVIGATION_KEYS = new Set([
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "Home",
  "End",
  "PageDown",
  "PageUp",
  "Enter",
  " ",
]);

export function KeyboardNavigation() {
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.keyboardNavigation = "false";

    function handleKeyDown(event: KeyboardEvent): void {
      if (event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }

      const isEditingText =
        event.target instanceof HTMLElement &&
        (event.target.isContentEditable ||
          event.target.closest('input:not([type="checkbox"]):not([type="radio"]), textarea') !==
            null);

      if (event.key === "Tab" || (!isEditingText && NAVIGATION_KEYS.has(event.key))) {
        root.dataset.keyboardNavigation = "true";
      }
    }

    function handlePointerDown(): void {
      root.dataset.keyboardNavigation = "false";
    }

    document.addEventListener("keydown", handleKeyDown, true);
    document.addEventListener("pointerdown", handlePointerDown, true);

    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);
      document.removeEventListener("pointerdown", handlePointerDown, true);
      delete root.dataset.keyboardNavigation;
    };
  }, []);

  return null;
}
