"""Check Etch startup prerequisites and prepare JWT keys; no Python dependencies."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
COMPOSE_FILES = {
    "dev": "docker-compose-dev.yml",
    "test": "docker-compose-test.yml",
    "prod": "docker-compose-prod.yml",
}
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
    for target, example in (
        (".env", ".env.example"),
        ("backend/.env", "backend/.env.example"),
        ("frontend/.env", "frontend/.env.example"),
        ("redis/users.acl", "redis/users.acl.example"),
    ):
        destination = ROOT / target
        if destination.exists() or destination.is_symlink():
            require_path(destination)
            continue
        source = ROOT / example
        require_path(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Redis reads the bind-mounted ACL as its own container user.
            mode = 0o644 if target.endswith(".acl") else 0o600
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


def check_project(profile: str) -> None:
    compose = ROOT / COMPOSE_FILES[profile]
    require_path(compose)
    ensure_config_files()
    backend_env = "backend/.env.test" if profile == "test" else "backend/.env"
    if not (ROOT / backend_env).is_file():
        raise SetupError(
            f"missing {backend_env}. copy backend/.env.example to {backend_env} "
            "and configure values for test."
        )
    require_path(ROOT / backend_env)
    for directory in ("backend/app", "backend/alembic", "frontend/src"):
        require_path(ROOT / directory, "directory")
    for filename in (
        "backend/pyproject.toml",
        "backend/uv.lock",
        "backend/alembic.ini",
        "frontend/package.json",
        "frontend/package-lock.json",
    ):
        require_path(ROOT / filename)
    require_tool("docker")
    try:
        run(["docker", "compose", "version"])
    except SetupError as exc:
        raise SetupError(
            "docker compose is unavailable. install the compose plugin."
        ) from exc
    try:
        run(["docker", "info", "--format", "{{.ServerVersion}}"])
    except SetupError as exc:
        raise SetupError(
            "the docker daemon is unavailable. start docker and check access permissions."
        ) from exc
    try:
        config = json.loads(
            run(
                [
                    "docker",
                    "compose",
                    "--project-directory",
                    str(ROOT),
                    "-f",
                    str(compose),
                    "config",
                    "--format",
                    "json",
                ]
            )
        )
    except (SetupError, json.JSONDecodeError) as exc:
        raise SetupError(
            f"invalid configuration in {compose.name}. check compose and required values in the env files."
        ) from exc

    api_env = {
        key.lower(): value
        for key, value in config["services"]["api"].get("environment", {}).items()
    }
    missing = [key for key in REQUIRED_API_ENV if not api_env.get(key)]
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

    cert_directory = ROOT / "backend/certs"
    for service in config["services"].values():
        build = service.get("build")
        if build:
            context = Path(build["context"])
            require_path(context, "directory")
            require_path(context / build.get("dockerfile", "Dockerfile"))
        for volume in service.get("volumes", []):
            if volume["type"] == "bind" and Path(volume["source"]) != cert_directory:
                source = Path(volume["source"])
                require_path(source, "directory" if source.is_dir() else "file")

    ensure_certs(interactive=True)
    print(
        f"{profile} checks passed. the application can start; run migrations separately."
    )


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
