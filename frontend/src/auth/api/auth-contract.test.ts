import { describe, expect, it } from "vitest";
import { parseCurrentUser } from "./auth-contract";

describe("auth contract", () => {
  it("maps /users/me to the frontend user model", () => {
    expect(
      parseCurrentUser({
        uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
        username: "alice",
        email: "alice@example.com",
      }),
    ).toEqual({
      uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
      username: "alice",
      email: "alice@example.com",
    });
  });

  it("does not expose extra backend fields through the user model", () => {
    expect(
      parseCurrentUser({
        uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
        username: "alice",
        email: "alice@example.com",
        hashed_password: "must-not-leak-into-ui-state",
      }),
    ).not.toHaveProperty("hashed_password");
  });

  it("rejects an invalid /users/me response", () => {
    expect(() => parseCurrentUser({ uuid: "user-id", username: "alice" })).toThrowError(
      expect.objectContaining({ code: "INVALID_USER_RESPONSE" }),
    );
  });
});
