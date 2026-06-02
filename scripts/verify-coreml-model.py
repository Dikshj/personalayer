#!/usr/bin/env python3
"""Build-time verification that Core ML model is present in production native builds.

Usage:
    python scripts/verify-coreml-model.py --platform ios
"""
import argparse
import sys
from pathlib import Path


def find_model(platform: str, search_root: Path) -> Path | None:
    suffix = ".mlpackage"
    name = "all-MiniLM-L6-v2"
    for p in search_root.rglob(f"*{suffix}"):
        if name in p.name:
            return p
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify CoreML model presence")
    parser.add_argument("--platform", required=True, choices=["ios"])
    parser.add_argument("--search-root", type=Path, default=Path("native/ios"))
    args = parser.parse_args()

    model = find_model(args.platform, args.search_root)
    if model:
        print(f"[OK] CoreML model found: {model}")
        return 0
    else:
        print(f"[FAIL] CoreML model not found for {args.platform} under {args.search_root}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
