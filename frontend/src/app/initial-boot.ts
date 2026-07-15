type BootRootElement = Pick<HTMLElement, "removeAttribute">;
type BootLoaderElement = Pick<HTMLElement, "remove">;

export function completeInitialBoot(
  rootElement: BootRootElement | null,
  bootLoaderElement: BootLoaderElement | null,
): void {
  if (!rootElement) {
    return;
  }

  rootElement.removeAttribute("data-booting");
  rootElement.removeAttribute("aria-hidden");
  rootElement.removeAttribute("inert");
  bootLoaderElement?.remove();
}
