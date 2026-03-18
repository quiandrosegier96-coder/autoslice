#!/usr/bin/env python3
"""
AutoSlice version manager.

Keeps all version declarations in sync across:
  - frontend/package.json
  - backend/pyproject.toml
  - backend/app/main.py
  - frontend/src/app/(auth)/login/page.tsx

Usage
-----
  python scripts/version.py bump    # patch +1, update all files, git commit
  python scripts/version.py sync    # sync all files to package.json version
  python scripts/version.py show    # print current version and exit
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# ── Repo root (two levels up from scripts/) ───────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

# ── Files that contain a version declaration ──────────────────────────────────
#   (relative_path, search_regex, replacement_template)
VERSION_FILES: list[tuple[str, str, str]] = [
    (
        "frontend/package.json",
        r'"version":\s*"[\d.]+"',
        '"version": "{ver}"',
    ),
    (
        "backend/pyproject.toml",
        r'^version\s*=\s*"[\d.]+"',
        'version = "{ver}"',
    ),
    (
        "backend/app/main.py",
        r'version\s*=\s*"[\d.]+"',
        'version="{ver}"',
    ),
    (
        "frontend/src/app/(auth)/login/page.tsx",
        r'AutoSlice v[\d.]+',
        'AutoSlice v{ver}',
    ),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_version() -> str:
    """Read the authoritative version from package.json."""
    pkg = ROOT / "frontend" / "package.json"
    return json.loads(pkg.read_text(encoding="utf-8"))["version"]


def bump_patch(version: str) -> str:
    parts = version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def write_all(version: str) -> list[str]:
    """
    Write version to every file in VERSION_FILES.
    Returns a list of paths that were actually changed.
    """
    changed: list[str] = []
    for rel, pattern, template in VERSION_FILES:
        path = ROOT / rel
        if not path.exists():
            print(f"  [skip] {rel} not found")
            continue
        original = path.read_text(encoding="utf-8")
        replacement = template.format(ver=version)
        updated = re.sub(pattern, replacement, original, flags=re.MULTILINE)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed.append(rel)
            print(f"  [ok]   {rel}")
        else:
            print(f"  [--]   {rel} already at v{version}")
    return changed


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def git_commit_version(version: str) -> None:
    """Stage version files and create a version-bump commit."""
    files = [str(ROOT / rel) for rel, _, _ in VERSION_FILES if (ROOT / rel).exists()]
    git("add", *files)
    result = git("commit", "-m", f"chore: bump to v{version} [skip ci]")
    if result.returncode == 0:
        print(f"  [git]  committed: chore: bump to v{version}")
    else:
        # Nothing new to commit is not an error
        msg = result.stderr.strip() or result.stdout.strip()
        if "nothing to commit" not in msg:
            print(f"  [git]  {msg}")


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_show() -> None:
    print(read_version())


def cmd_sync() -> None:
    ver = read_version()
    print(f"Syncing all files to v{ver} ...")
    write_all(ver)


def cmd_bump() -> None:
    # Skip if the last commit was already a version bump (prevents push-loop)
    last_msg = git("log", "-1", "--format=%s").stdout.strip()
    if last_msg.startswith("chore: bump to v") and "[skip ci]" in last_msg:
        print("Last commit is already a version bump — skipping.")
        return

    current = read_version()
    new_ver  = bump_patch(current)
    print(f"Bumping v{current} -> v{new_ver} ...")
    changed = write_all(new_ver)
    if changed:
        git_commit_version(new_ver)
    else:
        print("No files changed — nothing to commit.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "sync"
    {"bump": cmd_bump, "sync": cmd_sync, "show": cmd_show}.get(command, cmd_sync)()
