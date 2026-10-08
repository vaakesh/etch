import { test as base, expect } from "@playwright/test";
import type { ConsoleMessage, Request, Response, WebError } from "@playwright/test";

interface ExpectedHttpError {
  method: string;
  pathname: string;
  status: number;
  reason: string;
}

interface ExpectedRequestFailure {
  method: string;
  pathname: string;
  reason: string;
}

export class BrowserDiagnostics {
  readonly errors: string[] = [];
  private readonly expectedHttpErrors: ExpectedHttpError[] = [];
  private readonly expectedRequestFailures: ExpectedRequestFailure[] = [];
  private readonly expectedFailureUrls = new Set<string>();
  private readonly responses: Response[] = [];
  private readonly consoleErrors: ConsoleMessage[] = [];

  expectHttpError(error: ExpectedHttpError): void {
    if (!error.reason.trim()) throw new Error("Expected HTTP errors require a reason");
    this.expectedHttpErrors.push(error);
  }

  // Transport failure a scenario causes on purpose (route.abort); everything else still fails.
  expectRequestFailure(failure: ExpectedRequestFailure): void {
    if (!failure.reason.trim()) throw new Error("Expected request failures require a reason");
    this.expectedRequestFailures.push(failure);
  }

  onConsole = (message: ConsoleMessage): void => {
    if (message.type() === "error") this.consoleErrors.push(message);
  };
  onWebError = (error: WebError): void => {
    this.errors.push(`Page error: ${error.error().message}`);
  };
  onResponse = (response: Response): void => {
    if (response.status() >= 400) this.responses.push(response);
  };
  onRequestFailed = (request: Request): void => {
    const failure = request.failure()?.errorText ?? "Unknown network failure";
    // Navigation and AbortController cancellations are not transport failures.
    if (/ERR_ABORTED|NS_BINDING_ABORTED|cancelled|canceled/i.test(failure)) return;
    const pathname = new URL(request.url()).pathname;
    const isExpected = this.expectedRequestFailures.some(
      (expected) => request.method() === expected.method && pathname === expected.pathname,
    );
    if (isExpected) {
      this.expectedFailureUrls.add(request.url());
      return;
    }
    this.errors.push(`Request failed: ${request.method()} ${request.url()} (${failure})`);
  };

  problems(): string[] {
    const problems = [...this.errors];
    for (const message of this.consoleErrors) {
      const url = message.location().url;
      const text = message.text();
      const isResourceError = /^Failed to load resource:/.test(text);
      if (isResourceError && this.expectedFailureUrls.has(url)) continue;
      const isExpectedResourceError =
        isResourceError &&
        this.responses.some(
          (response) =>
            response.url() === url &&
            this.expectedHttpErrors.some(
              (expected) =>
                response.request().method() === expected.method &&
                new URL(response.url()).pathname === expected.pathname &&
                response.status() === expected.status,
            ),
        );
      if (!isExpectedResourceError) problems.push(`Console error: ${text} (${url})`);
    }
    return problems;
  }
}

export const test = base.extend<{ diagnostics: BrowserDiagnostics }>({
  diagnostics: [
    async ({ context }, runFixture, testInfo) => {
      const diagnostics = new BrowserDiagnostics();
      context.on("console", diagnostics.onConsole);
      context.on("weberror", diagnostics.onWebError);
      context.on("response", diagnostics.onResponse);
      context.on("requestfailed", diagnostics.onRequestFailed);
      try {
        await runFixture(diagnostics);
      } finally {
        context.off("console", diagnostics.onConsole);
        context.off("weberror", diagnostics.onWebError);
        context.off("response", diagnostics.onResponse);
        context.off("requestfailed", diagnostics.onRequestFailed);
        const problems = diagnostics.problems();
        if (problems.length) {
          await testInfo.attach("browser-errors", {
            body: problems.join("\n"),
            contentType: "text/plain",
          });
        }
        expect(problems, "Unexpected browser errors").toEqual([]);
      }
    },
    { auto: true },
  ],
});
export { expect };
