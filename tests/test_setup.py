"""Startup preparation tests using only the Python standard library."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

import setup


class SetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_pem = setup.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:2048",
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private.pem"
            setup.write_new(private, cls.private_pem, 0o600)
            cls.public_pem = setup.run(
                ["openssl", "pkey", "-in", str(private), "-pubout"]
            )
            private.unlink()
            other = setup.run(
                [
                    "openssl",
                    "genpkey",
                    "-algorithm",
                    "RSA",
                    "-pkeyopt",
                    "rsa_keygen_bits:2048",
                ]
            )
            setup.write_new(private, other, 0o600)
            cls.other_public_pem = setup.run(
                ["openssl", "pkey", "-in", str(private), "-pubout"]
            )

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory = self.root / "backend/certs"
        self.private = self.directory / "jwt-private.pem"
        self.public = self.directory / "jwt-public.pem"
        root_patch = patch.object(setup, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.output = io.StringIO()
        capture = redirect_stdout(self.output)
        capture.__enter__()
        self.addCleanup(capture.__exit__, None, None, None)

    def install_keys(self, public=True):
        self.directory.mkdir(parents=True)
        setup.write_new(self.private, self.private_pem, 0o600)
        if public:
            setup.write_new(self.public, self.public_pem, 0o644)

    def project_config(self, profile="dev"):
        for directory in (
            "backend/app",
            "backend/alembic",
            "frontend/src",
            "redis",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        for filename in (
            f"docker-compose-{profile}.yml",
            ".env",
            "backend/.env",
            "frontend/.env",
            "backend/pyproject.toml",
            "backend/uv.lock",
            "backend/alembic.ini",
            "frontend/package.json",
            "frontend/package-lock.json",
            "redis/users.acl",
        ):
            (self.root / filename).write_text("fixture", encoding="utf-8")
        environment = dict.fromkeys(setup.REQUIRED_API_ENV, "secret-must-not-appear")
        environment.update(
            {
                "db_port": "5432",
                "redis_port": "6379",
                "auth_jwt__private_key_path": "/backend/certs/jwt-private.pem",
                "auth_jwt__public_key_path": "/backend/certs/jwt-public.pem",
            }
        )
        return {"services": {"api": {"environment": environment}}}

    def docker_runner(self, config):
        original = setup.run

        def run(command):
            if command[0] == "docker":
                return json.dumps(config).encode() if "config" in command else b"ok"
            return original(command)

        return patch.object(setup, "run", side_effect=run)

    def install_config_templates(self):
        templates = {
            ".env.example": b"db_password=mock-root-secret\n",
            "backend/.env.example": b"redis_password=mock-backend-secret\n",
            "frontend/.env.example": b"VITE_API_URL=/api\nVITE_PROXY_TARGET=http://api:8000\n",
            "redis/users.acl.example": b"user admin on >mock-acl-secret +@all\n",
        }
        for filename, contents in templates.items():
            path = self.root / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        return templates

    def test_missing_configs_are_copied_exactly_and_logged_without_values(self):
        templates = self.install_config_templates()
        setup.ensure_config_files()
        for example, contents in templates.items():
            target = self.root / example.removesuffix(".example")
            self.assertEqual(target.read_bytes(), contents)
            expected_mode = 0o644 if target.suffix == ".acl" else 0o600
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), expected_mode)
            self.assertIn(
                f"{example} → {target.relative_to(self.root)}", self.output.getvalue()
            )
        self.assertNotIn("mock-root-secret", self.output.getvalue())
        self.assertNotIn("mock-backend-secret", self.output.getvalue())
        self.assertNotIn("mock-acl-secret", self.output.getvalue())

    def test_existing_configs_are_preserved_when_templates_change(self):
        templates = self.install_config_templates()
        setup.ensure_config_files()
        before = {}
        for example in templates:
            target = self.root / example.removesuffix(".example")
            before[target] = (target.read_bytes(), target.stat().st_mtime_ns)
            (self.root / example).write_bytes(b"changed template")
        self.output.seek(0)
        self.output.truncate()
        setup.ensure_config_files()
        for target, original in before.items():
            self.assertEqual((target.read_bytes(), target.stat().st_mtime_ns), original)
        self.assertEqual(self.output.getvalue(), "")

    def test_partial_configuration_copies_only_missing_files(self):
        self.install_config_templates()
        (self.root / ".env").write_bytes(b"developer configuration")
        setup.ensure_config_files()
        self.assertEqual((self.root / ".env").read_bytes(), b"developer configuration")
        self.assertEqual(self.output.getvalue().count("automatically copied"), 3)
        self.assertTrue((self.root / "backend/.env").is_file())
        self.assertTrue((self.root / "frontend/.env").is_file())
        self.assertTrue((self.root / "redis/users.acl").is_file())

    def test_config_directory_is_not_replaced_by_file(self):
        self.install_config_templates()
        (self.root / ".env").mkdir()
        with self.assertRaises(setup.SetupError):
            setup.ensure_config_files()
        self.assertTrue((self.root / ".env").is_dir())

    def test_config_dangling_symlink_is_not_replaced(self):
        self.install_config_templates()
        target = self.root / "missing"
        (self.root / ".env").symlink_to(target)
        with self.assertRaises(setup.SetupError):
            setup.ensure_config_files()
        self.assertTrue((self.root / ".env").is_symlink())
        self.assertFalse(target.exists())

    def test_existing_configs_do_not_require_example_files(self):
        self.project_config()
        setup.ensure_config_files()
        self.assertEqual(self.output.getvalue(), "")

    def test_explicit_generation_and_repeat_preserve_existing_private(self):
        setup.ensure_certs(interactive=False)
        original = self.private.read_bytes()
        original_stat = self.private.stat()
        setup.ensure_certs(interactive=False)
        self.assertEqual(self.private.read_bytes(), original)
        self.assertEqual(self.private.stat().st_mtime_ns, original_stat.st_mtime_ns)
        self.assertEqual(stat.S_IMODE(self.private.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.public.stat().st_mode), 0o644)
        self.assertNotIn("BEGIN PRIVATE KEY", self.output.getvalue())

    def test_missing_keys_without_terminal_fail_without_writing(self):
        with patch.object(setup.sys.stdin, "isatty", return_value=False):
            with self.assertRaisesRegex(setup.SetupError, "make certs"):
                setup.ensure_certs(interactive=True)
        self.assertFalse(self.directory.exists())

    def test_interactive_generation_requires_confirmation(self):
        with (
            patch.object(setup.sys.stdin, "isatty", return_value=True),
            patch("builtins.input", return_value="yes"),
        ):
            setup.ensure_certs(interactive=True)
        self.assertTrue(self.private.is_file())
        self.assertTrue(self.public.is_file())

    def test_declined_generation_creates_nothing(self):
        with (
            patch.object(setup.sys.stdin, "isatty", return_value=True),
            patch("builtins.input", return_value="n"),
        ):
            with self.assertRaisesRegex(setup.SetupError, "cancelled"):
                setup.ensure_certs(interactive=True)
        self.assertFalse(self.directory.exists())

    def test_public_recovery_preserves_private(self):
        self.install_keys(public=False)
        setup.ensure_certs(interactive=False)
        self.assertEqual(self.private.read_bytes(), self.private_pem)
        self.assertEqual(self.public.read_bytes(), self.public_pem)

    def test_public_without_private_is_preserved(self):
        self.directory.mkdir(parents=True)
        setup.write_new(self.public, self.public_pem, 0o644)
        with self.assertRaisesRegex(setup.SetupError, "private key is missing"):
            setup.ensure_certs(interactive=False)
        self.assertFalse(self.private.exists())
        self.assertEqual(self.public.read_bytes(), self.public_pem)

    def test_mismatched_keys_are_not_replaced(self):
        self.install_keys(public=False)
        setup.write_new(self.public, self.other_public_pem, 0o644)
        with self.assertRaisesRegex(setup.SetupError, "do not match"):
            setup.ensure_certs(interactive=False)
        self.assertEqual(self.private.read_bytes(), self.private_pem)
        self.assertEqual(self.public.read_bytes(), self.other_public_pem)

    def test_corrupt_private_is_not_replaced(self):
        self.directory.mkdir(parents=True)
        setup.write_new(self.private, b"broken key", 0o600)
        with self.assertRaisesRegex(setup.SetupError, "invalid"):
            setup.ensure_certs(interactive=False)
        self.assertEqual(self.private.read_bytes(), b"broken key")
        self.assertFalse(self.public.exists())

    def test_corrupt_public_is_not_replaced(self):
        self.install_keys(public=False)
        setup.write_new(self.public, b"broken public", 0o644)
        with self.assertRaisesRegex(setup.SetupError, "invalid"):
            setup.ensure_certs(interactive=False)
        self.assertEqual(self.public.read_bytes(), b"broken public")

    def test_existing_private_permissions_are_preserved_without_confirmation(self):
        self.install_keys()
        self.private.chmod(0o644)
        with patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
            for interactive in (False, True):
                with self.subTest(interactive=interactive):
                    setup.ensure_certs(interactive=interactive)
                    self.assertEqual(stat.S_IMODE(self.private.stat().st_mode), 0o644)
        self.assertEqual(self.private.read_bytes(), self.private_pem)

    def test_atomic_publish_never_overwrites_and_cleans_temporary_file(self):
        self.install_keys()
        with self.assertRaises(FileExistsError):
            setup.write_new(self.private, b"replacement", 0o600)
        self.assertEqual(self.private.read_bytes(), self.private_pem)
        self.assertEqual(
            sorted(path.name for path in self.directory.iterdir()),
            ["jwt-private.pem", "jwt-public.pem"],
        )

    def test_symlink_is_not_followed(self):
        self.directory.mkdir(parents=True)
        self.private.symlink_to(self.root / "missing")
        with self.assertRaisesRegex(setup.SetupError, "symlink"):
            setup.ensure_certs(interactive=False)
        self.assertFalse((self.root / "missing").exists())

    def test_valid_project_does_not_print_environment_secrets(self):
        config = self.project_config()
        self.install_keys()
        with self.docker_runner(config), patch.object(setup, "require_tool"):
            setup.check_project("dev")
        self.assertIn("dev checks passed", self.output.getvalue())
        self.assertNotIn("secret-must-not-appear", self.output.getvalue())

    def test_prod_check_accepts_manually_configured_key_ownership_and_permissions(self):
        config = self.project_config("prod")
        self.install_keys()
        self.private.chmod(0o644)
        original_stat = Path.stat

        def manually_configured_stat(path, *args, **kwargs):
            metadata = original_stat(path, *args, **kwargs)
            if path in (self.directory, self.private, self.public):
                values = list(metadata)
                values[4] = 4242  # st_uid
                values[5] = 4242  # st_gid
                return os.stat_result(values)
            return metadata

        with (
            self.docker_runner(config),
            patch.object(setup, "require_tool"),
            patch.object(Path, "stat", manually_configured_stat),
            patch("builtins.input", side_effect=AssertionError("unexpected prompt")),
        ):
            setup.check_project("prod")
        self.assertIn("prod checks passed", self.output.getvalue())
        self.assertEqual(stat.S_IMODE(self.private.stat().st_mode), 0o644)
        self.assertEqual(self.private.read_bytes(), self.private_pem)

    def test_missing_bind_mount_stops_before_generating_keys(self):
        config = self.project_config()
        config["services"]["api"]["volumes"] = [
            {"type": "bind", "source": str(self.root / "missing.ini")}
        ]
        with self.docker_runner(config), patch.object(setup, "require_tool"):
            with self.assertRaisesRegex(setup.SetupError, "missing.ini"):
                setup.check_project("dev")
        self.assertFalse(self.directory.exists())

    def test_missing_environment_setting_stops_before_generating_keys(self):
        config = self.project_config()
        config["services"]["api"]["environment"].pop("refresh_pepper")
        with self.docker_runner(config), patch.object(setup, "require_tool"):
            with self.assertRaisesRegex(setup.SetupError, "refresh_pepper"):
                setup.check_project("dev")
        self.assertFalse(self.directory.exists())

    def test_invalid_port_stops_before_generating_keys(self):
        config = self.project_config()
        config["services"]["api"]["environment"]["redis_port"] = "70000"
        with self.docker_runner(config), patch.object(setup, "require_tool"):
            with self.assertRaisesRegex(setup.SetupError, "redis_port"):
                setup.check_project("dev")
        self.assertFalse(self.directory.exists())

    def test_missing_template_stops_preparation_without_running_docker(self):
        (self.root / "docker-compose-prod.yml").touch()
        with patch.object(setup, "run") as run:
            with self.assertRaisesRegex(setup.SetupError, r"\.env.example"):
                setup.check_project("prod")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
