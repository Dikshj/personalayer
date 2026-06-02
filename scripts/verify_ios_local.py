from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


REQUIRED_TABLES = {
    "raw_event",
    "kg_node",
    "kg_edge",
    "temporal_chain",
    "domain_approval",
    "shared_bundle",
    "pcl_app",
    "pcl_permission",
    "pcl_integration",
    "push_token",
    "notification_route",
    "query_log",
    "feature_signal",
    "privacy_boundary",
}


def verify_ios_project(project_dir: Path, run_swift_build: bool = False) -> dict:
    project_dir = project_dir.resolve()
    package = project_dir / "Package.swift"
    schema = project_dir / "Sources" / "PersonalLayer" / "Storage" / "GRDBDatabase.swift"
    if not package.exists():
        return {"status": "error", "error": "package_missing", "path": str(package)}
    if not schema.exists():
        return {"status": "error", "error": "schema_missing", "path": str(schema)}

    text = schema.read_text(encoding="utf-8")
    migrations = re.findall(r'registerMigration\("v(\d+)_([^"]+)"\)', text)
    numbers = [int(number) for number, _ in migrations]
    expected = list(range(1, len(numbers) + 1))
    tables = set(re.findall(r'create\(table: "([^"]+)"', text))
    result = {
        "status": "ok",
        "migration_count": len(migrations),
        "migration_numbers": numbers,
        "migration_sequence_ok": numbers == expected,
        "missing_tables": sorted(REQUIRED_TABLES - tables),
        "swift_available": shutil.which("swift") is not None,
        "swift_build": "not_run",
    }
    if not result["migration_sequence_ok"] or result["missing_tables"]:
        result["status"] = "error"
    if run_swift_build and result["swift_available"]:
        completed = subprocess.run(
            ["swift", "build"],
            cwd=project_dir,
            text=True,
            capture_output=True,
            timeout=180,
        )
        result["swift_build"] = "ok" if completed.returncode == 0 else "failed"
        result["swift_build_output"] = (completed.stdout + completed.stderr)[-4000:]
        if completed.returncode != 0:
            result["status"] = "error"
    elif run_swift_build:
        result["swift_build"] = "swift_not_available"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify local iOS package and GRDB migration schema.")
    parser.add_argument("--project-dir", default="native/ios/PersonalLayer")
    parser.add_argument("--swift-build", action="store_true")
    args = parser.parse_args()
    result = verify_ios_project(Path(args.project_dir), run_swift_build=args.swift_build)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
