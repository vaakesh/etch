import { useCallback, useEffect, useEffectEvent, useRef, useState } from "react";
import { recordPracticeActivity } from "../api/practice-api";
import {
  PracticeActivityController,
  type PracticeActivityPhase,
} from "./practice-activity-controller";

const POINTER_MOVE_THROTTLE_MS = 1_000;

export interface UsePracticeActivityResult {
  phase: PracticeActivityPhase;
  focusRevision: number;
  resume: () => void;
  noteAnswerAccepted: (isFinished: boolean) => void;
}

interface UsePracticeActivityOptions {
  enabled: boolean;
  sessionUuid: string;
  onSessionUnavailable: () => void;
}

function canTrackCurrentPage(): boolean {
  return document.visibilityState === "visible" && document.hasFocus();
}

export function usePracticeActivity({
  enabled,
  onSessionUnavailable,
  sessionUuid,
}: UsePracticeActivityOptions): UsePracticeActivityResult {
  const [phase, setPhase] = useState<PracticeActivityPhase>("active");
  const [focusRevision, setFocusRevision] = useState(0);
  const controllerRef = useRef<PracticeActivityController | null>(null);
  const notifySessionUnavailable = useEffectEvent(() => onSessionUnavailable());

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const controller = new PracticeActivityController({
      request: (input, options) => recordPracticeActivity(sessionUuid, input, options),
      onPhaseChange: setPhase,
      onSessionUnavailable: notifySessionUnavailable,
    });
    controllerRef.current = controller;

    let lastPointerMoveAt = 0;
    const noteInteraction = (): void => controller.noteInteraction();
    const handlePointerMove = (): void => {
      const now = Date.now();
      if (now - lastPointerMoveAt >= POINTER_MOVE_THROTTLE_MS) {
        lastPointerMoveAt = now;
        noteInteraction();
      }
    };
    const handleVisibilityChange = (): void => {
      if (document.visibilityState !== "visible") {
        controller.pause({ keepalive: true });
      }
    };
    const handleWindowBlur = (): void => controller.pause({ keepalive: true });
    const handlePageHide = (): void => controller.pause({ keepalive: true });
    const handleOnline = (): void => controller.reconnect();

    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("pointerdown", noteInteraction, { passive: true });
    window.addEventListener("keydown", noteInteraction);
    window.addEventListener("wheel", noteInteraction, { passive: true });
    window.addEventListener("scroll", noteInteraction, { capture: true, passive: true });
    window.addEventListener("touchstart", noteInteraction, { passive: true });
    window.addEventListener("input", noteInteraction);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("blur", handleWindowBlur);
    window.addEventListener("pagehide", handlePageHide);
    window.addEventListener("online", handleOnline);

    if (canTrackCurrentPage()) {
      controller.activate();
    } else {
      controller.pause();
    }

    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerdown", noteInteraction);
      window.removeEventListener("keydown", noteInteraction);
      window.removeEventListener("wheel", noteInteraction);
      window.removeEventListener("scroll", noteInteraction, true);
      window.removeEventListener("touchstart", noteInteraction);
      window.removeEventListener("input", noteInteraction);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("blur", handleWindowBlur);
      window.removeEventListener("pagehide", handlePageHide);
      window.removeEventListener("online", handleOnline);
      controller.dispose();
      if (controllerRef.current === controller) {
        controllerRef.current = null;
      }
    };
  }, [enabled, sessionUuid]);

  const resume = useCallback(() => {
    if (!canTrackCurrentPage()) {
      return;
    }

    controllerRef.current?.activate();
    setFocusRevision((revision) => revision + 1);
  }, []);

  const noteAnswerAccepted = useCallback((isFinished: boolean) => {
    controllerRef.current?.noteAnswerAccepted(isFinished);
  }, []);

  return {
    phase: enabled ? phase : "active",
    focusRevision,
    resume,
    noteAnswerAccepted,
  };
}
