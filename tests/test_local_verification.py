import importlib.util
from pathlib import Path


def _load_script(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_extension_package_verification():
    verifier = _load_script("scripts/verify_extension_package.py")

    result = verifier.verify_extension(Path("extension"))

    assert result["status"] == "ok"
    assert result["manifest_version"] == 3
    assert result["missing_files"] == []


def test_ios_local_schema_verification_without_swift_build():
    verifier = _load_script("scripts/verify_ios_local.py")

    result = verifier.verify_ios_project(Path("native/ios/PersonalLayer"), run_swift_build=False)

    assert result["status"] == "ok"
    assert result["migration_sequence_ok"] is True
    assert result["missing_tables"] == []
