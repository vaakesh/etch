"""Check Etch startup prerequisites and prepare JWT keys; no Python dependencies."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent
COMPOSE_FILES = {
    "dev": "docker-compose-dev.yml",
    "test": "docker-compose-test.yml",
    "observability": "docker-compose-observability.yml",
}
# Redis and Prometheus read bind-mounted files as container users.
CONFIG_TEMPLATES = (
    (".env", ".env.example", 0o600),
    ("backend/.env", "backend/.env.example", 0o600),
    ("frontend/.env", "frontend/.env.example", 0o600),
    ("redis/users.acl", "redis/users.acl.example", 0o644),
    ("prometheus/metrics_token", "prometheus/metrics_token.example", 0o644),
)
SOURCE_DIRECTORIES = ("backend/app", "backend/alembic", "frontend/src")
SOURCE_FILES = (
    "backend/pyproject.toml",
    "backend/uv.lock",
    "backend/alembic.ini",
    "frontend/package.json",
    "frontend/package-lock.json",
)
REQUIRED_API_ENV = (
    "db_host",
    "db_port",
    "db_name",
    "db_user",
    "db_password",
    "redis_name",
    "redis_port",
    "redis_user",
    "redis_password",
    "refresh_pepper",
    "metrics_token",
    "celery_broker_url",
    "altcha_hmac_key",
    "auth_jwt__private_key_path",
    "auth_jwt__public_key_path",
)


class SetupError(Exception):
    pass


def run(command: list[str]) -> bytes:
    # Capture output to keep secrets and PEM contents out of terminal/logs.
    try:
        result = subprocess.run(command, capture_output=True, input=b"", timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SetupError(
            f"could not run {command[0]}; check its installation and availability."
        ) from exc
    if result.returncode:
        raise SetupError(f"command {command[0]} failed.")
    return result.stdout


def docker(*args: str, failure: str) -> bytes:
    try:
        return run(["docker", *args])
    except SetupError as exc:
        raise SetupError(failure) from exc


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise SetupError(f"{name} was not found. install it and retry the command.")


def confirm(message: str) -> None:
    if not sys.stdin.isatty():
        raise SetupError(f"{message} run make certs to prepare the keys.")
    answer = input(f"{message} [y/n]: ").strip().lower()
    if answer not in {"y", "yes"}:
        raise SetupError("setup cancelled. application startup stopped.")


def write_new(path: Path, contents: bytes, mode: int) -> None:
    # Publish a complete file atomically; never replace an existing key.
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            os.fchmod(stream.fileno(), mode)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            temporary.unlink()


def private_public_key(private: Path) -> bytes:
    try:
        run(
            [
                "openssl",
                "rsa",
                "-in",
                str(private),
                "-passin",
                "pass:",
                "-check",
                "-noout",
            ]
        )
        return run(
            [
                "openssl",
                "pkey",
                "-in",
                str(private),
                "-passin",
                "pass:",
                "-pubout",
                "-outform",
                "DER",
            ]
        )
    except SetupError as exc:
        raise SetupError(
            "the private jwt key is invalid, encrypted, or not an rsa key. the key was not changed."
        ) from exc


def ensure_certs(interactive: bool) -> None:
    require_tool("openssl")
    directory = ROOT / "backend/certs"
    private = directory / "jwt-private.pem"
    public = directory / "jwt-public.pem"
    created_private = False
    for path in (directory, private, public):
        if path.is_symlink():
            raise SetupError(
                f"{path.relative_to(ROOT)} is a symlink; check the path manually."
            )
    if directory.exists() and not directory.is_dir():
        raise SetupError("backend/certs must be a directory.")
    if not private.exists():
        if public.exists():
            raise SetupError(
                "the public key exists, but the private key is missing. restore the private key from a backup; the public key was preserved."
            )
        if interactive:
            confirm(
                "jwt keys are missing. create backend/certs and generate an rsa key pair?"
            )
        directory.mkdir(mode=0o755, parents=True, exist_ok=True)
        key = run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:2048",
            ]
        )
        write_new(private, key, 0o600)
        created_private = True
        print("created backend/certs/jwt-private.pem.")

    expected = private_public_key(private)
    if not public.exists():
        if interactive and not created_private:
            confirm(
                "the public jwt key is missing. restore it from the existing private key?"
            )
        contents = run(
            ["openssl", "pkey", "-in", str(private), "-passin", "pass:", "-pubout"]
        )
        write_new(public, contents, 0o644)
        print("created backend/certs/jwt-public.pem.")
    try:
        actual = run(
            [
                "openssl",
                "pkey",
                "-pubin",
                "-in",
                str(public),
                "-pubout",
                "-outform",
                "DER",
            ]
        )
    except SetupError as exc:
        raise SetupError(
            "the public jwt key is invalid. existing keys were not changed."
        ) from exc
    if expected != actual:
        raise SetupError(
            "the private and public jwt keys do not match. existing keys were not changed."
        )
    print("jwt keys are valid and match each other.")


def require_path(path: Path, kind: str = "file") -> None:
    valid = path.is_dir() if kind == "directory" else path.is_file()
    if not valid or not os.access(path, os.R_OK):
        raise SetupError(f"missing or inaccessible {kind}: {path}.")


def ensure_config_files() -> None:
    for target, example, mode in CONFIG_TEMPLATES:
        destination = ROOT / target
        if destination.exists() or destination.is_symlink():
            require_path(destination)
            continue
        source = ROOT / example
        require_path(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            write_new(destination, source.read_bytes(), mode)
        except FileExistsError:
            # Another setup process may have already created the configuration.
            require_path(destination)
            continue
        print(
            f"automatically copied {example} → {target} "
            f"(using values from the template). replace the template values in {target} "
            "with your own configuration before starting the application."
        )


def require_sources(backend_env: str) -> None:
    require_path(ROOT / backend_env)
    for directory in SOURCE_DIRECTORIES:
        require_path(ROOT / directory, "directory")
    for filename in SOURCE_FILES:
        require_path(ROOT / filename)


def check_docker() -> None:
    require_tool("docker")
    docker(
        "compose",
        "version",
        failure="docker compose is unavailable. install the compose plugin.",
    )
    docker(
        "info",
        "--format",
        "{{.ServerVersion}}",
        failure="the docker daemon is unavailable. start docker and check access permissions.",
    )


def compose_config(compose: Path, *options: str) -> dict:
    output = docker(
        "compose",
        "--project-directory",
        str(ROOT),
        "-f",
        str(compose),
        "config",
        "--format",
        "json",
        *options,
        failure=(
            f"invalid configuration in {compose.name}. "
            "check compose and required values in the env files."
        ),
    )
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise SetupError(f"could not read the configuration of {compose.name}.") from exc


def env_file_names(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        name, _, value = line.strip().partition("=")
        if value and not name.startswith("#"):
            names.add(name.strip())
    return names


def check_compose_variables(compose: Path) -> None:
    # Compose replaces an unset variable with an empty string and only warns about it.
    defined = env_file_names(ROOT / ".env") | {
        name for name, value in os.environ.items() if value
    }
    missing = sorted(
        name
        for name, variable in compose_config(compose, "--variables").items()
        if not variable["DefaultValue"] and name not in defined
    )
    if missing:
        raise SetupError(
            f"missing values in .env for {compose.name}: " + ", ".join(missing) + "."
        )


def check_api_settings(api_env: dict) -> None:
    missing = [
        key for key in REQUIRED_API_ENV if not str(api_env.get(key) or "").strip()
    ]
    if missing:
        raise SetupError("missing required api settings: " + ", ".join(missing) + ".")
    for key in ("db_port", "redis_port"):
        value = str(api_env[key])
        if not value.isdecimal() or not 1 <= int(value) <= 65535:
            raise SetupError(f"{key} must be a number between 1 and 65535.")
    for key, filename in (
        ("auth_jwt__private_key_path", "jwt-private.pem"),
        ("auth_jwt__public_key_path", "jwt-public.pem"),
    ):
        if api_env[key] != f"/backend/certs/{filename}":
            raise SetupError(
                f"for the current docker configuration, set {key}=/backend/certs/{filename}."
            )


def redis_acl_accepts(user: str, password: str) -> bool:
    acl = (ROOT / "redis/users.acl").read_text(encoding="utf-8")
    for line in acl.splitlines():
        tokens = line.split()
        if tokens[:2] == ["user", user]:
            # A hashed password cannot be compared with the plain value.
            return f">{password}" in tokens or any(t.startswith("#") for t in tokens)
    return False


def check_matching_settings(services: dict, api_env: dict, profile: str) -> None:
    mismatched = []
    postgres = services.get("postgres", {}).get("environment", {})
    for setting, variable in (
        ("db_name", "POSTGRES_DB"),
        ("db_user", "POSTGRES_USER"),
        ("db_password", "POSTGRES_PASSWORD"),
    ):
        if postgres and api_env[setting] != postgres.get(variable):
            mismatched.append(setting)

    rabbitmq = services.get("rabbitmq", {}).get("environment", {})
    if rabbitmq:
        broker = urlsplit(api_env["celery_broker_url"])
        credentials = (unquote(broker.username or ""), unquote(broker.password or ""))
        if credentials != (
            rabbitmq.get("RABBITMQ_DEFAULT_USER"),
            rabbitmq.get("RABBITMQ_DEFAULT_PASS"),
        ):
            mismatched.append("celery_broker_url")

    # The test stack mounts its own ACL and has no Prometheus.
    if profile == "dev":
        token = (ROOT / "prometheus/metrics_token").read_text(encoding="utf-8")
        if api_env["metrics_token"] != token.strip():
            mismatched.append("metrics_token")
        if not redis_acl_accepts(api_env["redis_user"], api_env["redis_password"]):
            mismatched.append("redis_password")

    if mismatched:
        raise SetupError(
            "these backend settings do not match the rest of the configuration: "
            + ", ".join(mismatched)
            + ". see the manual setup section of README.md."
        )


def check_build_and_mounts(services: dict) -> None:
    cert_directory = ROOT / "backend/certs"
    for service in services.values():
        build = service.get("build")
        if build:
            context = Path(build["context"])
            require_path(context, "directory")
            require_path(context / build.get("dockerfile", "Dockerfile"))
        for volume in service.get("volumes", []):
            if volume["type"] == "bind" and Path(volume["source"]) != cert_directory:
                source = Path(volume["source"])
                require_path(source, "directory" if source.is_dir() else "file")


def check_project(profile: str) -> None:
    compose = ROOT / COMPOSE_FILES[profile]
    application = profile != "observability"
    require_path(compose)
    ensure_config_files()
    if application:
        require_sources("backend/.env.test" if profile == "test" else "backend/.env")
    check_docker()
    check_compose_variables(compose)
    services = compose_config(compose)["services"]
    if application:
        api_env = {
            key.lower(): value
            for key, value in services["api"].get("environment", {}).items()
        }
        check_api_settings(api_env)
        check_matching_settings(services, api_env, profile)
    check_build_and_mounts(services)
    if application:
        ensure_certs(interactive=True)
    print(f"{profile} checks passed.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="check the project before docker compose startup and prepare jwt keys."
    )
    parser.add_argument(
        "action", choices=("check", "certs"), nargs="?", default="check"
    )
    parser.add_argument(
        "profile", choices=tuple(COMPOSE_FILES), nargs="?", default="dev"
    )
    args = parser.parse_args()
    try:
        if args.action == "certs":
            ensure_certs(interactive=False)
        else:
            check_project(args.profile)
    except (SetupError, OSError, EOFError) as exc:
        print(f"setup failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nsetup cancelled.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
