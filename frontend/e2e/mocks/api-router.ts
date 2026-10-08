import type { BrowserContext, Route, Request } from "@playwright/test";

export interface MockRequest {
  route: Route;
  request: Request;
  url: URL;
}
type Handler = (input: MockRequest) => Promise<void>;

export interface ResponseGate {
  /** Awaited by a handler before it fulfils: the request is received, the response is held. */
  opened: Promise<void>;
  open(): void;
}

export class ApiMockRouter {
  private readonly handlers = new Map<string, Handler>();
  private readonly gates: ResponseGate[] = [];
  readonly unexpected: string[] = [];
  private readonly origin: string;

  constructor(baseURL: string) {
    this.origin = new URL(baseURL).origin;
  }

  // Paths are backend paths without /api; query/body validation belongs to the handler.
  on(method: string, path: string, handler: Handler): void {
    if (!path.startsWith("/") || path.includes("?")) throw new Error("Use pathname without query");
    this.handlers.set(`${method.toUpperCase()} ${path}`, handler);
  }

  // Deferred response for loading/pending assertions; the fixture opens leftovers at teardown.
  gate(): ResponseGate {
    let open = (): void => {};
    const opened = new Promise<void>((resolve) => {
      open = resolve;
    });
    const gate = { opened, open };
    this.gates.push(gate);
    return gate;
  }

  openAllGates(): void {
    for (const gate of this.gates) gate.open();
  }

  async install(context: BrowserContext): Promise<void> {
    await context.route(
      (url) =>
        url.origin === this.origin && (url.pathname === "/api" || url.pathname.startsWith("/api/")),
      async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        const key = `${request.method()} ${url.pathname.slice(4)}`;
        const handler = this.handlers.get(key);
        if (!handler) {
          this.unexpected.push(`${request.method()} ${url.pathname}${url.search}`);
          await route.abort("blockedbyclient");
          return;
        }
        await handler({ route, request, url });
      },
    );
  }
}
