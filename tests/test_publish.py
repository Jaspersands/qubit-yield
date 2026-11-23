"""Publication safety tests. All process execution is mocked; no remote is contacted."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publish_existing.py"
REPO = "Jaspersands/qubit-yield"
COMMIT = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture
def publication(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("qubityield_publish_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / "source"
    contents = {"README.md": b"Verified project\n", "src/qubityield/value.py": b"VALUE = 42\n"}
    for name, data in contents.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    manifest = {"schema_version": 1, "algorithm": "SHA-256", "files": {
        name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        for name, data in contents.items()
    }}
    (root / "artifacts").mkdir()
    (root / "artifacts/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module.shutil, "which", lambda tool: f"/mock/bin/{tool}")

    def forbid_real_process(*args, **kwargs):
        pytest.fail("Publication tests must never launch a process or contact a remote")

    monkeypatch.setattr(module.subprocess, "run", forbid_real_process)
    return module, root, manifest, contents


class Commands:
    def __init__(self, module, monkeypatch, *, setup=None, changed=True):
        self.calls = []
        self.setup = setup
        self.changed = changed
        self.checkout = None
        self.snapshot = None
        self.fail_push = False
        self.remote_commit = COMMIT
        self.user = {"login": "Jaspersands", "id": 123, "name": "Jasper Sands"}
        self.repository = {"nameWithOwner": REPO, "visibility": "PUBLIC",
                           "defaultBranchRef": {"name": "main"}}
        monkeypatch.setattr(module, "command", self)

    def __call__(self, *args, cwd=None):
        self.calls.append((args, cwd))
        if args == ("gh", "auth", "status", "--hostname", "github.com"):
            return "Authenticated"
        if args == ("gh", "api", "user", "--hostname", "github.com"):
            return json.dumps(self.user)
        if args[:3] == ("gh", "repo", "view"):
            return json.dumps(self.repository)
        if args[:3] == ("gh", "repo", "clone"):
            self.checkout = Path(args[4])
            self.checkout.mkdir()
            (self.checkout / "unrelated-remote.txt").write_text("Preserve existing history and files\n")
            if self.setup is not None:
                self.setup(self.checkout)
            return "Cloned"
        if args[:3] == ("git", "--literal-pathspecs", "add"):
            self.snapshot = {
                name: (cwd / name).read_bytes() for name in args[4:]
            }
            self.snapshot["unrelated-remote.txt"] = (cwd / "unrelated-remote.txt").read_bytes()
            return ""
        if args == ("git", "diff", "--cached", "--name-only"):
            return "README.md" if self.changed else ""
        if args[0] == "git" and "commit" in args:
            return "Committed"
        if args == ("git", "rev-parse", "HEAD"):
            return COMMIT
        if args == ("git", "push", "origin", "HEAD:main"):
            if self.fail_push:
                raise subprocess.CalledProcessError(1, args, stderr="secret-that-must-not-be-echoed")
            return "Pushed"
        if args == ("git", "ls-remote", "origin", "refs/heads/main"):
            return f"{self.remote_commit}\trefs/heads/main" if self.remote_commit else ""
        pytest.fail(f"Unexpected publication command: {args!r}")

    def has(self, *prefix):
        return any(args[:len(prefix)] == prefix for args, _ in self.calls)


def test_dry_run_verifies_only_local_files_without_any_command(publication, monkeypatch, capsys):
    module, _, _, _ = publication
    commands = Commands(module, monkeypatch)
    assert module.main([]) == 0
    assert commands.calls == []
    output = capsys.readouterr().out
    assert '"force_push": false' in output
    assert "No remote action performed" in output
    assert REPO in output


def test_github_host_is_explicit_even_when_environment_selects_another_host(publication, monkeypatch):
    module, _, _, _ = publication
    monkeypatch.setenv("GH_HOST", "enterprise.example.invalid")
    commands = Commands(module, monkeypatch)
    assert module.main(["--push"]) == 0
    for args, _ in commands.calls:
        if args[0] != "gh":
            continue
        if args[1] in {"auth", "api"}:
            assert args[-2:] == ("--hostname", "github.com")
        else:
            assert args[1:3] in {("repo", "view"), ("repo", "clone")}
            assert args[3] == f"https://github.com/{REPO}"


@pytest.mark.parametrize("change", ["owner", "visibility", "repository", "empty_branch"])
def test_remote_identity_or_visibility_mismatch_stops_before_clone(publication, monkeypatch, change):
    module, _, _, _ = publication
    commands = Commands(module, monkeypatch)
    if change == "owner":
        commands.user["login"] = "DifferentPerson"
    elif change == "visibility":
        commands.repository["visibility"] = "PRIVATE"
    elif change == "repository":
        commands.repository["nameWithOwner"] = "Jaspersands/another-project"
    else:
        commands.repository["defaultBranchRef"] = None
    assert module.main(["--push"]) == 2
    assert not commands.has("gh", "repo", "clone")
    assert not commands.has("git")


@pytest.mark.parametrize("target", ["README.md", "src"])
def test_remote_file_and_parent_symlinks_are_refused(publication, monkeypatch, tmp_path, target):
    module, _, _, _ = publication
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "README.md"
    sentinel.write_text("must stay unchanged")

    def setup(checkout):
        (checkout / target).symlink_to(sentinel if target == "README.md" else outside,
                                      target_is_directory=target == "src")

    commands = Commands(module, monkeypatch, setup=setup)
    assert module.main(["--push"]) == 2
    assert not commands.has("git")
    assert sentinel.read_text() == "must stay unchanged"


def test_remote_directory_at_a_declared_file_path_is_not_silently_nested(publication, monkeypatch):
    module, _, _, _ = publication
    commands = Commands(module, monkeypatch, setup=lambda checkout: (checkout / "README.md").mkdir())
    assert module.main(["--push"]) == 2
    assert not commands.has("git")


def test_unrelated_platform_symlink_ancestor_does_not_block_checkout(publication, monkeypatch, tmp_path):
    module, _, _, _ = publication
    real = tmp_path / "real-temporary-parent"
    real.mkdir()
    alias = tmp_path / "platform-alias"
    alias.symlink_to(real, target_is_directory=True)
    temporary = alias / "publication"
    temporary.mkdir()

    class PlatformTemporaryDirectory:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return str(temporary)

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(module.tempfile, "TemporaryDirectory", PlatformTemporaryDirectory)
    commands = Commands(module, monkeypatch)
    assert module.main(["--push"]) == 0
    assert commands.has("git", "push")


@pytest.mark.parametrize("change", ["content", "missing", "digest"])
def test_manifest_tampering_stops_before_authentication(publication, monkeypatch, change):
    module, root, manifest, _ = publication
    commands = Commands(module, monkeypatch)
    if change == "content":
        (root / "README.md").write_text("Unverified changed content")
    elif change == "missing":
        (root / "README.md").unlink()
    else:
        manifest["files"]["README.md"]["sha256"] = "0" * 64
        (root / "artifacts/manifest.json").write_text(json.dumps(manifest))
    assert module.main(["--push"]) == 2
    assert commands.calls == []


def test_source_change_during_clone_fails_final_verification_before_staging(publication, monkeypatch):
    module, root, _, _ = publication
    commands = Commands(module, monkeypatch,
                        setup=lambda checkout: (root / "README.md").write_text("Changed during network wait"))
    assert module.main(["--push"]) == 2
    assert not commands.has("git")


def test_source_manifest_change_during_clone_cannot_replace_validated_manifest(publication, monkeypatch):
    module, root, manifest, _ = publication
    commands = Commands(module, monkeypatch,
                        setup=lambda checkout: (root / "artifacts/manifest.json").write_text('{"files":{}}'))
    assert module.main(["--push"]) == 0
    assert json.loads(commands.snapshot["artifacts/manifest.json"]) == manifest


@pytest.mark.parametrize("name", [".git/config", ".GIT/config"])
def test_manifest_cannot_overwrite_git_control_files(publication, monkeypatch, name):
    module, root, manifest, _ = publication
    control = root / name
    control.parent.mkdir()
    data = b"Untrusted Git config"
    control.write_bytes(data)
    manifest["files"][name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    (root / "artifacts/manifest.json").write_text(json.dumps(manifest))
    commands = Commands(module, monkeypatch)
    assert module.main(["--push"]) == 2
    assert commands.calls == []


def test_success_overlays_only_declared_files_and_uses_one_normal_push(publication, monkeypatch):
    module, root, manifest, contents = publication
    (root / "private-notes.txt").write_text("Unlisted local content")
    commands = Commands(module, monkeypatch)
    assert module.main(["--push"]) == 0
    expected_paths = sorted([*manifest["files"], "artifacts/manifest.json"])
    add = next(args for args, _ in commands.calls if args[:3] == ("git", "--literal-pathspecs", "add"))
    assert list(add[4:]) == expected_paths
    assert commands.snapshot["unrelated-remote.txt"] == b"Preserve existing history and files\n"
    assert "private-notes.txt" not in commands.snapshot
    for name, data in contents.items():
        assert commands.snapshot[name] == data
    pushes = [args for args, _ in commands.calls if args[:2] == ("git", "push")]
    assert pushes == [("git", "push", "origin", "HEAD:main")]
    assert not any("--force" in arg or arg.startswith("+") or arg == "--mirror"
                   for args in pushes for arg in args)
    assert not any(args[:2] in {("git", "init"), ("git", "reset")} for args, _ in commands.calls)


def test_denied_push_does_not_retry_with_force_or_echo_sensitive_stderr(publication, monkeypatch, capsys):
    module, _, _, _ = publication
    commands = Commands(module, monkeypatch)
    commands.fail_push = True
    assert module.main(["--push"]) == 2
    pushes = [args for args, _ in commands.calls if args[:2] == ("git", "push")]
    assert pushes == [("git", "push", "origin", "HEAD:main")]
    error = capsys.readouterr().err
    assert "No force-push was attempted" in error
    assert "secret-that-must-not-be-echoed" not in error


def test_unchanged_remote_creates_no_commit_or_push(publication, monkeypatch):
    module, _, _, _ = publication
    commands = Commands(module, monkeypatch, changed=False)
    assert module.main(["--push"]) == 0
    assert not commands.has("git", "push")
    assert not any("commit" in args for args, _ in commands.calls)


@pytest.mark.parametrize("remote_commit", ["f" * 40, ""])
def test_remote_commit_mismatch_does_not_claim_verified_success(publication, monkeypatch, capsys, remote_commit):
    module, _, _, _ = publication
    commands = Commands(module, monkeypatch)
    commands.remote_commit = remote_commit
    assert module.main(["--push"]) == 2
    output = capsys.readouterr()
    assert "could not be verified" in output.err
    assert "Published and verified commit" not in output.out
