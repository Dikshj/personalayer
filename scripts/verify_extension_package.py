from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


REQUIRED_MANIFEST_KEYS = {
    "manifest_version",
    "name",
    "version",
    "permissions",
    "background",
    "content_scripts",
    "action",
}


def verify_extension(extension_dir: Path, package: bool = False, output_dir: Path | None = None) -> dict:
    extension_dir = extension_dir.resolve()
    manifest_path = extension_dir / "manifest.json"
    if not manifest_path.exists():
        return {"status": "error", "error": "manifest_missing", "path": str(manifest_path)}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing_keys = sorted(REQUIRED_MANIFEST_KEYS - set(manifest))
    missing_files = _referenced_files(manifest)
    missing_files = [item for item in missing_files if not (extension_dir / item).exists()]
    result = {
        "status": "ok" if not missing_keys and not missing_files else "error",
        "manifest_version": manifest.get("manifest_version"),
        "version": manifest.get("version"),
        "missing_keys": missing_keys,
        "missing_files": missing_files,
        "package_path": "",
    }
    if result["status"] == "ok" and package:
        output_dir = (output_dir or extension_dir.parent / "dist").resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        package_path = output_dir / f"personal-layer-extension-{manifest['version']}.zip"
        with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(extension_dir.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(extension_dir).as_posix())
        result["package_path"] = str(package_path)
    return result


def _referenced_files(manifest: dict) -> list[str]:
    files: set[str] = set()
    background = manifest.get("background") or {}
    if background.get("service_worker"):
        files.add(background["service_worker"])
    for script in manifest.get("content_scripts") or []:
        for item in script.get("js") or []:
            files.add(item)
        for item in script.get("css") or []:
            files.add(item)
    action = manifest.get("action") or {}
    if action.get("default_popup"):
        files.add(action["default_popup"])
    icons = {**(manifest.get("icons") or {}), **(action.get("default_icon") or {})}
    for item in icons.values():
        files.add(item)
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and optionally package the Chrome extension.")
    parser.add_argument("--extension-dir", default="extension")
    parser.add_argument("--package", action="store_true")
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()
    result = verify_extension(
        Path(args.extension_dir),
        package=args.package,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
