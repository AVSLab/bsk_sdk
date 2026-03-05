from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


from scikit_build_core import build as _backend


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _required_sync_paths(repo_root: Path) -> list[Path]:
    sdk_src = repo_root / "src" / "bsk_sdk"
    return [
        sdk_src / "include" / "Basilisk",
        sdk_src / "arch_min",
        sdk_src / "runtime_min",
        sdk_src / "swig",
    ]


def _has_any_file(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    return any(child.is_file() for child in path.rglob("*"))


def _assert_synced_artifacts(repo_root: Path) -> None:
    missing = [p for p in _required_sync_paths(repo_root) if not _has_any_file(p)]
    if not missing:
        return

    missing_text = "\n".join(f"  - {p}" for p in missing)
    raise RuntimeError(
        "bsk-sdk vendored Basilisk artifacts are missing or empty:\n"
        f"{missing_text}\n\n"
        "Run this first:\n"
        "  python3 tools/sync_all.py --sync-submodules\n\n"
        "Or opt into auto-sync during build:\n"
        "  BSK_SDK_AUTO_SYNC=1 pip install -e ."
    )


def _run_sync() -> None:
    repo_root = Path(__file__).resolve().parent
    sync_script = repo_root / "tools" / "sync_all.py"
    if not sync_script.exists():
        return

    cmd = [sys.executable, str(sync_script)]

    if _truthy(os.environ.get("BSK_SDK_SYNC_SUBMODULES"), default=True):
        cmd.append("--sync-submodules")

    basilisk_root = os.environ.get("BSK_BASILISK_ROOT")
    if basilisk_root:
        cmd.extend(["--basilisk-root", basilisk_root])

    subprocess.run(cmd, cwd=repo_root, check=True)


def _prepare_artifacts() -> None:
    repo_root = Path(__file__).resolve().parent
    auto_sync = _truthy(os.environ.get("BSK_SDK_AUTO_SYNC"), default=False)
    if auto_sync:
        _run_sync()

    _assert_synced_artifacts(repo_root)


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, str] | None = None,
    metadata_directory: str | None = None,
) -> str:
    _prepare_artifacts()
    return _backend.build_wheel(
        wheel_directory, config_settings, metadata_directory
    )


def build_editable(
    wheel_directory: str,
    config_settings: dict[str, str] | None = None,
    metadata_directory: str | None = None,
) -> str:
    _prepare_artifacts()
    return _backend.build_editable(
        wheel_directory, config_settings, metadata_directory
    )


def build_sdist(
    sdist_directory: str,
    config_settings: dict[str, str] | None = None,
) -> str:
    _prepare_artifacts()
    return _backend.build_sdist(sdist_directory, config_settings)


def get_requires_for_build_wheel(
    config_settings: dict[str, str] | None = None,
) -> list[str]:
    return _backend.get_requires_for_build_wheel(config_settings)


def get_requires_for_build_editable(
    config_settings: dict[str, str] | None = None,
) -> list[str]:
    return _backend.get_requires_for_build_editable(config_settings)


def get_requires_for_build_sdist(
    config_settings: dict[str, str] | None = None,
) -> list[str]:
    return _backend.get_requires_for_build_sdist(config_settings)


def prepare_metadata_for_build_wheel(
    metadata_directory: str,
    config_settings: dict[str, str] | None = None,
) -> str:
    return _backend.prepare_metadata_for_build_wheel(
        metadata_directory, config_settings
    )


def prepare_metadata_for_build_editable(
    metadata_directory: str,
    config_settings: dict[str, str] | None = None,
) -> str:
    return _backend.prepare_metadata_for_build_editable(
        metadata_directory, config_settings
    )
