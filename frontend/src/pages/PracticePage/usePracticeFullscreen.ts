import { useEffect, useLayoutEffect, useRef, useState } from "react";

export function usePracticeFullscreen() {
  const sessionRef = useRef<HTMLElement>(null);
  const ownedElementRef = useRef<HTMLElement | null>(null);
  const activeRef = useRef(false);
  const nativeEnteredRef = useRef(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  function exitFullscreen(): void {
    activeRef.current = false;
    setIsFullscreen(false);
    if (document.fullscreenElement === ownedElementRef.current && document.fullscreenElement) {
      void document.exitFullscreen().catch(() => undefined);
    }
  }

  function toggleFullscreen(): void {
    if (activeRef.current) {
      exitFullscreen();
      return;
    }

    const session = sessionRef.current;
    if (session === null) {
      return;
    }
    // Keep the session itself free to resize when the on-screen keyboard opens.
    const target = session.closest<HTMLElement>("[data-practice-mode]") ?? session;
    ownedElementRef.current = target;
    activeRef.current = true;
    setIsFullscreen(true);

    if (typeof target.requestFullscreen === "function" && document.fullscreenEnabled) {
      void target
        .requestFullscreen({ navigationUI: "hide" })
        .then(() => {
          if (!activeRef.current && document.fullscreenElement === target) {
            void document.exitFullscreen().catch(() => undefined);
          }
        })
        .catch(() => {
          // The fitted session layout remains available when native fullscreen is denied.
        });
    }
  }

  useEffect(() => {
    const handleFullscreenChange = () => {
      if (document.fullscreenElement === ownedElementRef.current && document.fullscreenElement) {
        nativeEnteredRef.current = true;
      } else if (nativeEnteredRef.current) {
        nativeEnteredRef.current = false;
        activeRef.current = false;
        setIsFullscreen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && activeRef.current) {
        activeRef.current = false;
        setIsFullscreen(false);
        if (document.fullscreenElement === ownedElementRef.current && document.fullscreenElement) {
          void document.exitFullscreen().catch(() => undefined);
        }
      }
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      document.removeEventListener("keydown", handleEscape);
      activeRef.current = false;
      if (document.fullscreenElement === ownedElementRef.current && document.fullscreenElement) {
        void document.exitFullscreen().catch(() => undefined);
      }
    };
  }, []);

  useLayoutEffect(() => {
    const session = sessionRef.current;
    if (!isFullscreen || session === null) {
      return;
    }

    const viewport = window.visualViewport;
    const page = session.closest<HTMLElement>("[data-practice-mode]");
    const scrollTop = page?.scrollTop ?? 0;
    const scrollLeft = page?.scrollLeft ?? 0;
    page?.scrollTo(0, 0);
    const fitViewport = () => {
      const height = viewport?.height ?? window.innerHeight;
      session.style.setProperty("--session-viewport-height", `${height}px`);
      session.style.setProperty(
        "--session-viewport-width",
        `${viewport?.width ?? window.innerWidth}px`,
      );
      session.style.setProperty("--session-viewport-top", `${viewport?.offsetTop ?? 0}px`);
      session.style.setProperty("--session-viewport-left", `${viewport?.offsetLeft ?? 0}px`);
      session.dataset.compactViewport = height < 500 ? "true" : "false";
    };

    fitViewport();
    window.addEventListener("resize", fitViewport);
    viewport?.addEventListener("resize", fitViewport);
    viewport?.addEventListener("scroll", fitViewport);
    return () => {
      window.removeEventListener("resize", fitViewport);
      viewport?.removeEventListener("resize", fitViewport);
      viewport?.removeEventListener("scroll", fitViewport);
      for (const property of ["height", "width", "top", "left"]) {
        session.style.removeProperty(`--session-viewport-${property}`);
      }
      delete session.dataset.compactViewport;
      page?.scrollTo(scrollLeft, scrollTop);
    };
  }, [isFullscreen]);

  return { isFullscreen, sessionRef, toggleFullscreen };
}
