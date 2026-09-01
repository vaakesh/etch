import type { PracticeActivityInput, PracticeActivityResponse } from "./practice-types";

export const PRACTICE_HEARTBEAT_INTERVAL_MS = 10_000;
export const PRACTICE_IDLE_TIMEOUT_MS = 120_000;

const RETRY_DELAYS_MS = [2_000, 5_000, 10_000, 30_000] as const;

export type PracticeActivityPhase = "active" | "paused";

interface ActivityRequestOptions {
  keepalive?: boolean;
}

type ActivityRequest = (
  input: PracticeActivityInput,
  options?: ActivityRequestOptions,
) => Promise<PracticeActivityResponse>;

interface PracticeActivityControllerOptions {
  request: ActivityRequest;
  onPhaseChange: (phase: PracticeActivityPhase) => void;
  onSessionUnavailable: () => void;
}

type TimerHandle = ReturnType<typeof globalThis.setTimeout>;

export class PracticeActivityController {
  private readonly request: ActivityRequest;
  private readonly onPhaseChange: (phase: PracticeActivityPhase) => void;
  private readonly onSessionUnavailable: () => void;
  private trackerUuid: string | null = null;
  private heartbeatTimer: TimerHandle | null = null;
  private idleTimer: TimerHandle | null = null;
  private retryTimer: TimerHandle | null = null;
  private retryAttempt = 0;
  private requestRevision = 0;
  private isActive = false;
  private isDisposed = false;
  private didReportUnavailable = false;

  constructor(options: PracticeActivityControllerOptions) {
    this.request = options.request;
    this.onPhaseChange = options.onPhaseChange;
    this.onSessionUnavailable = options.onSessionUnavailable;
  }

  activate(): void {
    if (this.isDisposed) {
      return;
    }

    if (this.isActive) {
      this.noteInteraction();
      return;
    }

    this.isActive = true;
    this.onPhaseChange("active");
    this.resetIdleTimer();
    this.requestResume();
  }

  pause(options: ActivityRequestOptions = {}): void {
    if (this.isDisposed) {
      return;
    }

    const trackerUuid = this.trackerUuid;
    const wasActive = this.isActive;

    this.isActive = false;
    this.trackerUuid = null;
    this.requestRevision += 1;
    this.clearTimers();
    this.onPhaseChange("paused");

    if (!wasActive || trackerUuid === null) {
      return;
    }

    void this.request({ event: "pause", trackerUuid }, { keepalive: options.keepalive }).catch(
      () => undefined,
    );
  }

  noteInteraction(): void {
    if (!this.isActive || this.isDisposed) {
      return;
    }

    this.resetIdleTimer();
  }

  noteAnswerAccepted(isFinished: boolean): void {
    if (this.isDisposed) {
      return;
    }

    if (isFinished) {
      this.finish();
      return;
    }
    if (!this.isActive) {
      return;
    }

    this.requestRevision += 1;
    this.clearHeartbeatTimer();
    this.clearRetryTimer();
    this.retryAttempt = 0;
    this.resetIdleTimer();

    if (this.trackerUuid === null) {
      this.requestResume();
      return;
    }

    this.scheduleHeartbeat();
  }

  reconnect(): void {
    if (!this.isActive || this.isDisposed) {
      return;
    }

    this.requestRevision += 1;
    this.trackerUuid = null;
    this.clearHeartbeatTimer();
    this.clearRetryTimer();
    this.retryAttempt = 0;
    this.requestResume();
  }

  finish(): void {
    if (this.isDisposed) {
      return;
    }

    this.isActive = false;
    this.trackerUuid = null;
    this.requestRevision += 1;
    this.clearTimers();
  }

  dispose(): void {
    if (this.isDisposed) {
      return;
    }

    const trackerUuid = this.trackerUuid;
    const shouldPause = this.isActive && trackerUuid !== null;

    this.isDisposed = true;
    this.isActive = false;
    this.trackerUuid = null;
    this.requestRevision += 1;
    this.clearTimers();

    if (shouldPause) {
      void this.request({ event: "pause", trackerUuid }, { keepalive: true }).catch(
        () => undefined,
      );
    }
  }

  private requestResume(): void {
    if (!this.isActive || this.isDisposed) {
      return;
    }

    const revision = this.beginRequest();
    void this.request({ event: "resume" })
      .then((response) => {
        if (!this.isCurrentRequest(revision)) {
          return;
        }
        if (response.trackerUuid === null) {
          this.reportSessionUnavailable();
          return;
        }

        this.trackerUuid = response.trackerUuid;
        this.retryAttempt = 0;
        this.clearRetryTimer();
        this.scheduleHeartbeat();
      })
      .catch(() => {
        if (this.isCurrentRequest(revision)) {
          this.trackerUuid = null;
          this.scheduleResumeRetry();
        }
      });
  }

  private requestHeartbeat(): void {
    if (!this.isActive || this.isDisposed || this.trackerUuid === null) {
      return;
    }

    const trackerUuid = this.trackerUuid;
    const revision = this.beginRequest();
    void this.request({ event: "heartbeat", trackerUuid })
      .then((response) => {
        if (!this.isCurrentRequest(revision)) {
          return;
        }
        if (response.trackerUuid === null) {
          this.trackerUuid = null;
          this.requestResume();
          return;
        }

        this.trackerUuid = response.trackerUuid;
        this.retryAttempt = 0;
        this.scheduleHeartbeat();
      })
      .catch(() => {
        if (this.isCurrentRequest(revision)) {
          this.trackerUuid = null;
          this.scheduleResumeRetry();
        }
      });
  }

  private reportSessionUnavailable(): void {
    if (this.didReportUnavailable) {
      return;
    }

    this.didReportUnavailable = true;
    this.isActive = false;
    this.trackerUuid = null;
    this.clearTimers();
    this.onSessionUnavailable();
  }

  private scheduleHeartbeat(): void {
    if (!this.isActive || this.isDisposed || this.trackerUuid === null) {
      return;
    }

    this.clearHeartbeatTimer();
    this.heartbeatTimer = globalThis.setTimeout(() => {
      this.heartbeatTimer = null;
      this.requestHeartbeat();
    }, PRACTICE_HEARTBEAT_INTERVAL_MS);
  }

  private scheduleResumeRetry(): void {
    if (!this.isActive || this.isDisposed || this.retryTimer !== null) {
      return;
    }

    const delay = RETRY_DELAYS_MS[Math.min(this.retryAttempt, RETRY_DELAYS_MS.length - 1)];
    this.retryAttempt += 1;
    this.retryTimer = globalThis.setTimeout(() => {
      this.retryTimer = null;
      this.requestResume();
    }, delay);
  }

  private resetIdleTimer(): void {
    if (!this.isActive || this.isDisposed) {
      return;
    }

    this.clearIdleTimer();
    this.idleTimer = globalThis.setTimeout(() => {
      this.idleTimer = null;
      this.pause();
    }, PRACTICE_IDLE_TIMEOUT_MS);
  }

  private beginRequest(): number {
    this.requestRevision += 1;
    return this.requestRevision;
  }

  private isCurrentRequest(revision: number): boolean {
    return this.isActive && !this.isDisposed && revision === this.requestRevision;
  }

  private clearTimers(): void {
    this.clearHeartbeatTimer();
    this.clearIdleTimer();
    this.clearRetryTimer();
  }

  private clearHeartbeatTimer(): void {
    if (this.heartbeatTimer !== null) {
      globalThis.clearTimeout(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private clearIdleTimer(): void {
    if (this.idleTimer !== null) {
      globalThis.clearTimeout(this.idleTimer);
      this.idleTimer = null;
    }
  }

  private clearRetryTimer(): void {
    if (this.retryTimer !== null) {
      globalThis.clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
  }
}
