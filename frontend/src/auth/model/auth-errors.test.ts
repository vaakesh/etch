import { describe, expect, it } from "vitest";
import { ApiError } from "../../api";
import { isAuthSessionRejected } from "./auth-errors";

describe("isAuthSessionRejected", () => {
  it.each([401, 403, 404])("treats auth status %s as a rejected session", (status) => {
    expect(isAuthSessionRejected(new ApiError({ status, message: "Rejected" }))).toBe(true);
  });

  it.each([0, 422, 500, 503])("does not turn status %s into a logout", (status) => {
    expect(isAuthSessionRejected(new ApiError({ status, message: "Unavailable" }))).toBe(false);
  });

  it("does not classify an unknown client error as an auth rejection", () => {
    expect(isAuthSessionRejected(new Error("Broken contract"))).toBe(false);
  });
});
