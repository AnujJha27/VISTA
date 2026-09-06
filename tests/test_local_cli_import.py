"""research-readiness audit section 8: `dftcert.local_cli` (the `noether`/
`vista` console-script entrypoint) must actually be importable and able to
reach the `verify` subcommand on this project's primary dev toolchain
(Windows `python.exe`), not just under WSL. Two real module-level POSIX-only
imports (`curses`, and `fcntl` via `dftcert.legacy.pipeline`) previously
broke this entirely -- `python vista verify start ...` crashed before
parsing a single argument. Both are now deferred to only the legacy command
paths that actually need them.
"""
import unittest


class LocalCliImportTests(unittest.TestCase):
    def test_local_cli_module_imports_without_posix_only_dependencies(self):
        import dftcert.local_cli  # noqa: F401 -- the import itself is the test

    def test_verify_dispatch_reaches_the_real_verify_cli_not_an_import_crash(self):
        """A bogus but well-formed `verify start` call must fail with a real
        `ManifestError`-driven diagnostics exit (2), proving dispatch made
        it all the way into `dftcert.verification.cli` -- not an
        `ImportError`/`SystemExit` from unrelated legacy machinery that
        `verify` never needed to load in the first place."""
        from dftcert.local_cli import main

        rc = main([
            "verify", "start", "--extraction-result", "/does/not/exist.json",
            "--package", "/does/not/exist.json", "--session", "/does/not/exist/session.json",
            "--project", "/does/not/exist", "--trusted-local",
        ])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
