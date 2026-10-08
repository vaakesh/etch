import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const run = promisify(execFile);
const COMPOSE_FILE = fileURLToPath(new URL("../../../docker-compose-test.yml", import.meta.url));

// Runs inside the test API container: Redis credentials stay in its environment, and the
// database name proves it is the disposable test stand before anything is deleted.
const FLUSH_SCRIPT = `
import os, redis
if os.environ["db_name"] != "etch_test_integration":
    raise SystemExit("Refusing to flush Redis: not the test stand")
redis.Redis(
    host=os.environ["redis_name"],
    port=int(os.environ["redis_port"]),
    username=os.environ["redis_user"],
    password=os.environ["redis_password"],
).flushdb()
`;

/**
 * Empties Redis of the test stand: rate-limit counters (registration 5/hour, login 10/minute per
 * IP) and caches. Works only for the stand started from the repository's docker-compose-test.yml.
 */
export async function flushTestRedis(): Promise<void> {
  try {
    await run(
      "docker",
      [
        "compose",
        ...["-f", COMPOSE_FILE],
        ...["exec", "-T", "api"],
        ...["uv", "run", "--no-sync", "python", "-c", FLUSH_SCRIPT],
      ],
      { timeout: 20_000 },
    );
  } catch (error) {
    const details = error instanceof Error ? error.message : String(error);
    throw new Error(`Could not flush Redis of the test stand: ${details}`, { cause: error });
  }
}
