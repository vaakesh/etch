import { ApiError } from "../../api/api-error";
import { parseUserSettings } from "../../features/settings/model/settings-contract";
import type { User } from "../model/auth-types";

export class AuthContractError extends ApiError {
  constructor(code: string, message: string, options?: ErrorOptions) {
    super({ status: 0, code, message, cause: options?.cause });
    this.name = "AuthContractError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

export function parseCurrentUser(payload: unknown): User {
  if (
    !isRecord(payload) ||
    !isNonEmptyString(payload.uuid) ||
    !isNonEmptyString(payload.username) ||
    !isNonEmptyString(payload.email)
  ) {
    throw new AuthContractError(
      "INVALID_USER_RESPONSE",
      "The backend returned an unexpected user shape.",
    );
  }

  let settings: User["settings"];
  try {
    settings = parseUserSettings(payload.settings);
  } catch (error) {
    throw new AuthContractError(
      "INVALID_USER_RESPONSE",
      "The backend returned an unexpected user shape.",
      { cause: error },
    );
  }

  return {
    uuid: payload.uuid,
    username: payload.username,
    email: payload.email,
    settings,
  };
}
