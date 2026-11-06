import type { ApiMockRouter } from "./api-router";

const TRACKER_UUID = "01900000-0000-7000-8000-0000000000aa";

/**
 * An open practice session: `GET /bff/practice/{uuid}/resume` returns `session`,
 * and `POST /training-sessions/{uuid}/activity` accepts the study-time tracker.
 */
export function mockOpenPracticeSession(
  api: ApiMockRouter,
  sessionUuid: string,
  session: unknown,
): void {
  api.on("GET", `/bff/practice/${sessionUuid}/resume`, async ({ route }) => {
    await route.fulfill({ json: session });
  });
  api.on("POST", `/training-sessions/${sessionUuid}/activity`, async ({ route, request }) => {
    const body: unknown = request.postDataJSON();
    const isPause =
      typeof body === "object" && body !== null && "event" in body && body.event === "pause";
    await route.fulfill({ json: { tracker_uuid: isPause ? null : TRACKER_UUID } });
  });
}
