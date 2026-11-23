"""Publish the verified project into its existing public GitHub repository.

Requires an already authenticated GitHub CLI. Never reads browser credentials,
requests access scopes, force-pushes, or replaces the repository's history.
Without --push, prints the exact local publication plan and does not contact GitHub.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qubityield.portable import read_json, verify_manifest  # noqa: E402


def command(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="Jaspersands/qubit-yield")
    parser.add_argument("--push", action="store_true", help="Commit and push to the existing public repository")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", args.repo):
        parser.error("--repo must be an owner/name pair")
    try:
        manifest = read_json(ROOT / "artifacts" / "manifest.json", max_bytes=5_242_880)
        check = verify_manifest(manifest, ROOT)
        if not check["valid"]:
            print(json.dumps(check, indent=2))
            raise ValueError("Publication stopped: the project differs from its release manifest")
        paths = sorted([*manifest["files"], "artifacts/manifest.json"])
        if any(name.split("/")[0].casefold() == ".git" for name in paths):
            raise ValueError("A publication manifest must not contain Git control files")
        plan = {"repository": args.repo, "files": len(paths),
                "bytes": sum((ROOT / name).stat().st_size for name in paths),
                "action": "Overlay verified project files on a fresh checkout and push one normal commit",
                "preserves_unrelated_remote_files": True, "force_push": False}
        print(json.dumps(plan, indent=2))
        if not args.push:
            print("No remote action performed. Add --push only from an authenticated GitHub CLI environment.")
            return 0
        if shutil.which("gh") is None or shutil.which("git") is None:
            raise ValueError("Install the official GitHub CLI and Git before publishing")
        repository_url = f"https://github.com/{args.repo}"
        command("gh", "auth", "status", "--hostname", "github.com")
        user = json.loads(command("gh", "api", "user", "--hostname", "github.com"))
        owner = args.repo.split("/")[0]
        if user["login"].casefold() != owner.casefold():
            raise ValueError("Authenticated account does not match the requested personal repository owner")
        repository = json.loads(command("gh", "repo", "view", repository_url, "--json", "nameWithOwner,visibility,defaultBranchRef"))
        if repository["nameWithOwner"].casefold() != args.repo.casefold() or repository["visibility"] != "PUBLIC":
            raise ValueError("The selected repository must already exist and be public")
        branch_ref = repository.get("defaultBranchRef")
        if not isinstance(branch_ref, dict) or not isinstance(branch_ref.get("name"), str) or not branch_ref["name"]:
            raise ValueError("The existing repository must have a default branch before publication")
        branch = branch_ref["name"]
        with tempfile.TemporaryDirectory(prefix="qubityield-publish-") as directory:
            checkout = Path(directory) / "repository"
            command("gh", "repo", "clone", repository_url, str(checkout), "--", "--branch", branch, "--single-branch")
            for name in paths:
                destination = checkout / name
                for part in (destination, *destination.parents):
                    if part == checkout.parent:
                        break
                    if part.is_symlink():
                        raise ValueError(f"Remote symlink would redirect a project file: {name}")
                if not destination.resolve().is_relative_to(checkout.resolve()):
                    raise ValueError(f"Remote symlink would redirect a project file: {name}")
                if destination.exists() and not destination.is_file():
                    raise ValueError(f"Remote path is not a regular project file: {name}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                if name == "artifacts/manifest.json":
                    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                else:
                    shutil.copy2(ROOT / name, destination)
            copied_check = verify_manifest(manifest, checkout)
            if not copied_check["valid"]:
                raise ValueError("Publication stopped: copied files differ from the verified manifest; regenerate and retry")
            command("git", "--literal-pathspecs", "add", "--", *paths, cwd=checkout)
            if not command("git", "diff", "--cached", "--name-only", cwd=checkout):
                print("The public repository already contains this verified project.")
                return 0
            identity = ["-c", f"user.name={user.get('name') or user['login']}",
                        "-c", f"user.email={user['id']}+{user['login']}@users.noreply.github.com"]
            command("git", *identity, "commit", "-m", "Publish QubitYield 0.2 experiment workbench and verified evidence", cwd=checkout)
            commit = command("git", "rev-parse", "HEAD", cwd=checkout)
            command("git", "push", "origin", f"HEAD:{branch}", cwd=checkout)
            remote_fields = command("git", "ls-remote", "origin", f"refs/heads/{branch}", cwd=checkout).split()
            remote = remote_fields[0] if remote_fields else None
            if remote != commit:
                raise ValueError("Push finished but the remote branch could not be verified at the published commit")
            print(f"Published and verified commit {commit} at https://github.com/{args.repo}")
            print("GitHub Actions must still finish before the hosted demo is verified.")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"Publication stopped: {Path(exc.cmd[0]).name} exited {exc.returncode}. Check GitHub CLI authentication and repository write/workflow permissions. No force-push was attempted.", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError) as exc:
        print(f"Publication stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
