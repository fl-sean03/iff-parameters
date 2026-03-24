#!/usr/bin/env python3
"""Validate all bundles in the data directory."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


def validate_bundle(root: Path) -> list[str]:
    errors: list[str] = []
    mp = root / "manifest.json"
    if not mp.exists():
        return [f"Missing manifest.json in {root}"]

    try:
        manifest = json.loads(mp.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"Invalid manifest.json: {e}"]

    for field in ("name", "version", "tables", "sources"):
        if field not in manifest:
            errors.append(f"Missing manifest field: {field}")

    if "provenance" not in manifest:
        errors.append("Missing provenance metadata")
    else:
        for pf in ("author", "source_file", "source_sha256"):
            if not manifest["provenance"].get(pf):
                errors.append(f"Missing provenance.{pf}")

    try:
        from upm.bundle.io import load_package
        bundle = load_package(root)
        for tname, df in bundle.tables.items():
            if df is None or len(df) == 0:
                errors.append(f"Table '{tname}' is empty")
    except Exception as e:
        errors.append(f"Load failed: {e}")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate all IFF parameter bundles")
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve() if args.data_dir else _REPO_ROOT / "src" / "iff_parameters" / "data"
    manifests = sorted(data_dir.rglob("manifest.json"))

    if not manifests:
        print("No bundles found.")
        return

    print(f"Validating {len(manifests)} bundle(s)\n")
    total_errors = 0
    for mp in manifests:
        root = mp.parent
        rel = root.relative_to(data_dir)
        errors = validate_bundle(root)
        if errors:
            print(f"  FAIL  {rel}")
            for e in errors:
                print(f"        - {e}")
            total_errors += len(errors)
        else:
            print(f"  OK    {rel}")

    print(f"\n{'='*40}")
    if total_errors == 0:
        print(f"All {len(manifests)} bundle(s) passed.")
    else:
        print(f"{total_errors} error(s).")
        sys.exit(1)


if __name__ == "__main__":
    main()
