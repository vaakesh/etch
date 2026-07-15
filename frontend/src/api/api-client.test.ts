import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "./api-client";
import { ApiError } from "./api-error";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolvePromise!: (value: T | PromiseLike<T>) => void;
  let rejectPromise!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolve, reject) => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });

  return { promise, resolve: resolvePromise, reject: rejectPromise };
}

async function flushPromises(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

function createClient(fetchFn: typeof fetch) {
  return {
    client: new ApiClient({
      baseUrl: "/api",
      fetchFn,
    }),
  };
}

describe("ApiClient", () => {
  it("performs a typed successful request with query and a JSON body", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ id: "card-1" }));
    const { client } = createClient(fetchMock);

    const result = await client.request<{ id: string }, { front: string }>("/cards", {
      method: "POST",
      query: { limit: 10, tag: ["new", "daily"] },
      body: { front: "hello" },
    });

    expect(result).toEqual({ id: "card-1" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/cards?limit=10&tag=new&tag=daily");
    const init = fetchMock.mock.calls[0]?.[1];
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe('{"front":"hello"}');
    expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
  });

  it("refreshes after a 401 and retries the original request once", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ message: "Expired" }, 401))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    const refresh = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
    const { client } = createClient(fetchMock);
    client.configureSession({ refresh });

    await expect(client.request<{ ok: boolean }>("/profile")).resolves.toEqual({ ok: true });

    expect(refresh).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("uses one refresh for several simultaneous 401 responses", async () => {
    let requestCount = 0;
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => {
      requestCount += 1;
      return requestCount <= 3
        ? jsonResponse({ message: "Expired" }, 401)
        : jsonResponse({ ok: true });
    });
    const refreshResult = deferred<void>();
    const refresh = vi.fn(() => refreshResult.promise);
    const { client } = createClient(fetchMock);
    client.configureSession({ refresh });

    const requests = [
      client.request<{ ok: boolean }>("/one"),
      client.request<{ ok: boolean }>("/two"),
      client.request<{ ok: boolean }>("/three"),
    ];
    await flushPromises();

    expect(refresh).toHaveBeenCalledTimes(1);
    refreshResult.resolve(undefined);

    await expect(Promise.all(requests)).resolves.toEqual([
      { ok: true },
      { ok: true },
      { ok: true },
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(6);
  });

  it("reuses credentials from a completed refresh for a late original 401", async () => {
    const lateUnauthorized = deferred<Response>();
    let fastCalls = 0;
    let slowCalls = 0;
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/fast")) {
        fastCalls += 1;
        return fastCalls === 1
          ? jsonResponse({ message: "Expired" }, 401)
          : jsonResponse({ source: "fast" });
      }

      slowCalls += 1;
      return slowCalls === 1 ? lateUnauthorized.promise : jsonResponse({ source: "slow" });
    });
    const refresh = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
    const { client } = createClient(fetchMock);
    client.configureSession({ refresh });

    const fastRequest = client.request<{ source: string }>("/fast");
    const slowRequest = client.request<{ source: string }>("/slow");

    await expect(fastRequest).resolves.toEqual({ source: "fast" });
    expect(refresh).toHaveBeenCalledOnce();

    lateUnauthorized.resolve(jsonResponse({ message: "Expired later" }, 401));
    await expect(slowRequest).resolves.toEqual({ source: "slow" });

    expect(refresh).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("expires the session and rejects callers when refresh fails", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ message: "Expired" }, 401));
    const refreshError = new ApiError({
      status: 401,
      code: "REFRESH_REJECTED",
      message: "Refresh rejected",
    });
    const onUnauthorized = vi.fn();
    const { client } = createClient(fetchMock);
    client.configureSession({
      refresh: vi.fn().mockRejectedValue(refreshError),
      onUnauthorized,
    });

    await expect(client.request("/profile")).rejects.toBe(refreshError);
    expect(onUnauthorized).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("does not start a second refresh when the retried request is also 401", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ message: "Still unauthorized" }, 401));
    const refresh = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
    const onUnauthorized = vi.fn();
    const { client } = createClient(fetchMock);
    client.configureSession({ refresh, onUnauthorized });

    await expect(client.request("/profile")).rejects.toMatchObject({
      status: 401,
      message: "Still unauthorized",
    });
    expect(refresh).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("never recursively refreshes a refresh endpoint request", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ message: "Expired" }, 401))
      .mockResolvedValueOnce(jsonResponse({ message: "Refresh expired" }, 401));
    const { client } = createClient(fetchMock);
    const refresh = vi.fn(async () => {
      await client.request("/auth/refresh", {
        method: "POST",
        auth: false,
        retryOnUnauthorized: false,
      });
    });
    client.configureSession({ refresh });

    await expect(client.request("/profile")).rejects.toMatchObject({
      status: 401,
      message: "Refresh expired",
    });
    expect(refresh).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not restore a session or retry when logout happens during refresh", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ message: "Expired" }, 401));
    const refreshResult = deferred<void>();
    const onUnauthorized = vi.fn();
    const { client } = createClient(fetchMock);
    client.configureSession({
      refresh: vi.fn(() => refreshResult.promise),
      onUnauthorized,
    });

    const request = client.request("/profile");
    await flushPromises();
    client.invalidateSession();
    refreshResult.resolve(undefined);

    await expect(request).rejects.toMatchObject({ code: "SESSION_INVALIDATED" });
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it("maps a refresh transport that honors abort to session invalidation", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ message: "Expired" }, 401));
    const refresh = vi.fn(
      (signal: AbortSignal) =>
        new Promise<void>((_resolve, reject) => {
          signal.addEventListener("abort", () => reject(signal.reason), { once: true });
        }),
    );
    const { client } = createClient(fetchMock);
    client.configureSession({ refresh });

    const request = client.request("/profile");
    await flushPromises();
    client.invalidateSession();

    await expect(request).rejects.toMatchObject({ code: "SESSION_INVALIDATED" });
    expect(refresh).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("does not start refresh for an already aborted caller", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    const refresh = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
    const { client } = createClient(fetchMock);
    const controller = new AbortController();
    controller.abort("route-changed");
    client.configureSession({ refresh });

    await expect(client.refreshSession(controller.signal)).rejects.toMatchObject({
      status: 0,
      code: "REQUEST_ABORTED",
    });
    expect(refresh).not.toHaveBeenCalled();
  });

  it("returns undefined for a 204 response", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }));
    const { client } = createClient(fetchMock);

    await expect(client.request<void>("/logout", { method: "POST" })).resolves.toBeUndefined();
  });

  it("returns text for a successful non-JSON response", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        new Response("ready", { status: 200, headers: { "Content-Type": "text/plain" } }),
      );
    const { client } = createClient(fetchMock);

    await expect(client.request<string>("/health")).resolves.toBe("ready");
  });

  it("throws a typed protocol error for invalid JSON", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response("{broken", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const { client } = createClient(fetchMock);

    await expect(client.request("/broken")).rejects.toMatchObject({
      status: 200,
      code: "INVALID_JSON_RESPONSE",
    });
  });

  it("normalizes an abort while reading the response body", async () => {
    const abortedBody = new ReadableStream({
      start(controller) {
        controller.error(new DOMException("Aborted", "AbortError"));
      },
    });
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(abortedBody, {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const { client } = createClient(fetchMock);

    await expect(client.request("/stream")).rejects.toMatchObject({
      status: 0,
      code: "REQUEST_ABORTED",
    });
  });

  it("normalizes a custom AbortSignal reason from fetch", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(
      async (_input, init) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(init.signal?.reason), {
            once: true,
          });
        }),
    );
    const { client } = createClient(fetchMock);
    const controller = new AbortController();

    const request = client.request("/slow", { signal: controller.signal });
    controller.abort("route-changed");

    await expect(request).rejects.toMatchObject({
      status: 0,
      code: "REQUEST_ABORTED",
    });
  });

  it("does not set a JSON content type for FormData", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }));
    const { client } = createClient(fetchMock);
    const formData = new FormData();
    formData.set("image", new Blob(["data"], { type: "text/plain" }), "image.txt");

    await client.request<void, FormData>("/upload", { method: "POST", body: formData });

    const headers = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
    expect(headers.has("Content-Type")).toBe(false);
  });
});
