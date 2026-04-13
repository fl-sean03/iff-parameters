#!/usr/bin/env python3
"""Immutability check: ensure committed version directories aren't mutated.

Intended to run in PR CI. Uses `git diff --name-status origin/main...HEAD`
to find modified files under data/parameters/ or data/structures/, and fails
if any such file is an *edit* (M) or *rename* (R) of a file already present
on origin/main. New versions (added as entirely new subtrees) are fine.

This is advisory — the real source of truth is PR review. Fails loud only
when someone tries to edit the bytes of a previously-committed version
directory.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _git(*args: str) -> str:
    res = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return res.stdout


def _modified_files(base: str = "origin/main") -> list[tuple[str, str]]:
    """Return (status_code, path) tuples for files changed vs base."""
    # Ensure base ref exists locally
    try:
        _git("rev-parse", "--verify", base)
    except subprocess.CalledProcessError:
        # fallback to HEAD~1 (e.g., pushes on main)
        base = "HEAD~1"
        try:
            _git("rev-parse", "--verify", base)
        except subprocess.CalledProcessError:
            return []

    output = _git("diff", "--name-status", f"{base}...HEAD")
    rows: list[tuple[str, str]] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        path = parts[-1]
        rows.append((status, path))
    return rows


_VERSION_DIR = re.compile(r"data/(parameters|structures)/[^/]+/(.*?/)?v[0-9]+\.[0-9]+/")


def main() -> int:
    if not Path(".git").is_dir():
        print("not a git repository — skipping immutability check")
        return 0

    changes = _modified_files()
    violations: list[tuple[str, str]] = []
    for status, path in changes:
        if status.startswith(("M", "R")) and _VERSION_DIR.search(path):
            violations.append((status, path))

    if not violations:
        print("immutability OK — no existing version directories mutated")
        return 0

    print("immutability VIOLATIONS — these files inside existing version "
          "directories were modified:")
    for status, path in violations:
        print(f"  [{status}] {path}")
    print()
    print("Fix by creating a new version directory instead of editing the old one.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
