import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PracticeActivityInput, PracticeActivityResponse } from "./practice-types";
import {
  PracticeActivityController,
  PRACTICE_HEARTBEAT_INTERVAL_MS,
  PRACTICE_IDLE_TIMEOUT_MS,
  type PracticeActivityPhase,
} from "./practice-activity-controller";

const TRACKER_UUID = "019c05e5-bc86-70e6-8f5c-d31bfa1aac10";
const NEXT_TRACKER_UUID = "019c05e5-bc86-70e6-8f5c-d31bfa1aac11";

type ActivityRequest = (
  input: PracticeActivityInput,
  options?: { keepalive?: boolean },
) => Promise<PracticeActivityResponse>;

function createController(request: ActivityRequest) {
  const phases: PracticeActivityPhase[] = [];
  const onSessionUnavailable = vi.fn();
  const controller = new PracticeActivityController({
    request,
    onPhaseChange: (phase) => phases.push(phase),
    onSessionUnavailable,
  });

  return { controller, onSessionUnavailable, phases };
}

describe("PracticeActivityController", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("resumes immediately and sends heartbeats every ten seconds", async () => {
    const request = vi.fn<ActivityRequest>().mockResolvedValue({ trackerUuid: TRACKER_UUID });
    const { controller, phases } = createController(request);

    controller.activate();
    await vi.advanceTimersByTimeAsync(0);

    expect(phases).toEqual(["active"]);
    expect(request).toHaveBeenNthCalledWith(1, { event: "resume" });

    await vi.advanceTimersByTimeAsync(PRACTICE_HEARTBEAT_INTERVAL_MS - 1);
    expect(request).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1);
    expect(request).toHaveBeenNthCalledWith(2, {
      event: "heartbeat",
      trackerUuid: TRACKER_UUID,
    });

    await vi.advanceTimersByTimeAsync(PRACTICE_HEARTBEAT_INTERVAL_MS);
    expect(request).toHaveBeenNthCalledWith(3, {
      event: "heartbeat",
      trackerUuid: TRACKER_UUID,
    });
  });

  it("restarts the heartbeat countdown after a successful answer", async () => {
    const request = vi.fn<ActivityRequest>().mockResolvedValue({ trackerUuid: TRACKER_UUID });
    const { controller } = createController(request);

    controller.activate();
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(9_000);

    controller.noteAnswerAccepted(false);
    await vi.advanceTimersByTimeAsync(9_999);
    expect(request).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1);
    expect(request).toHaveBeenNthCalledWith(2, {
      event: "heartbeat",
      trackerUuid: TRACKER_UUID,
    });
  });

  it("pauses after two minutes without interaction and resets inactivity on activity", async () => {
    const request = vi.fn<ActivityRequest>().mockResolvedValue({ trackerUuid: TRACKER_UUID });
    const { controller, phases } = createController(request);

    controller.activate();
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(PRACTICE_IDLE_TIMEOUT_MS - 1);
    controller.noteInteraction();
    await vi.advanceTimersByTimeAsync(PRACTICE_IDLE_TIMEOUT_MS - 1);

    expect(phases).toEqual(["active"]);

    await vi.advanceTimersByTimeAsync(1);
    expect(phases).toEqual(["active", "paused"]);
    expect(request).toHaveBeenLastCalledWith(
      { event: "pause", trackerUuid: TRACKER_UUID },
      { keepalive: undefined },
    );
  });

  it("gets a new tracker when a heartbeat token is rejected", async () => {
    const request = vi
      .fn<ActivityRequest>()
      .mockResolvedValueOnce({ trackerUuid: TRACKER_UUID })
      .mockResolvedValueOnce({ trackerUuid: null })
      .mockResolvedValue({ trackerUuid: NEXT_TRACKER_UUID });
    const { controller, onSessionUnavailable } = createController(request);

    controller.activate();
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(PRACTICE_HEARTBEAT_INTERVAL_MS);

    expect(request).toHaveBeenNthCalledWith(2, {
      event: "heartbeat",
      trackerUuid: TRACKER_UUID,
    });
    expect(request).toHaveBeenNthCalledWith(3, { event: "resume" });
    expect(onSessionUnavailable).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(PRACTICE_HEARTBEAT_INTERVAL_MS);
    expect(request).toHaveBeenNthCalledWith(4, {
      event: "heartbeat",
      trackerUuid: NEXT_TRACKER_UUID,
    });
  });

  it("reports the session when tracker recovery also returns null", async () => {
    const request = vi
      .fn<ActivityRequest>()
      .mockResolvedValueOnce({ trackerUuid: TRACKER_UUID })
      .mockResolvedValueOnce({ trackerUuid: null })
      .mockResolvedValueOnce({ trackerUuid: null });
    const { controller, onSessionUnavailable } = createController(request);

    controller.activate();
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(PRACTICE_HEARTBEAT_INTERVAL_MS);

    expect(onSessionUnavailable).toHaveBeenCalledOnce();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(request).toHaveBeenCalledTimes(3);
  });

  it("retries transport failures in the background without pausing the UI", async () => {
    const request = vi
      .fn<ActivityRequest>()
      .mockRejectedValueOnce(new Error("network unavailable"))
      .mockResolvedValueOnce({ trackerUuid: TRACKER_UUID });
    const { controller, onSessionUnavailable, phases } = createController(request);

    controller.activate();
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(1_999);
    expect(request).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1);
    expect(request).toHaveBeenNthCalledWith(2, { event: "resume" });
    expect(phases).toEqual(["active"]);
    expect(onSessionUnavailable).not.toHaveBeenCalled();
  });

  it("sends a best-effort pause with keepalive when disposed", async () => {
    const request = vi.fn<ActivityRequest>().mockResolvedValue({ trackerUuid: TRACKER_UUID });
    const { controller } = createController(request);

    controller.activate();
    await vi.advanceTimersByTimeAsync(0);
    controller.dispose();

    expect(request).toHaveBeenLastCalledWith(
      { event: "pause", trackerUuid: TRACKER_UUID },
      { keepalive: true },
    );
  });

  it("does not send pause after the final answer finishes the session", async () => {
    const request = vi.fn<ActivityRequest>().mockResolvedValue({ trackerUuid: TRACKER_UUID });
    const { controller } = createController(request);

    controller.activate();
    await vi.advanceTimersByTimeAsync(0);
    controller.noteAnswerAccepted(true);
    controller.dispose();

    expect(request).toHaveBeenCalledTimes(1);
    expect(request).toHaveBeenCalledWith({ event: "resume" });
  });
});
