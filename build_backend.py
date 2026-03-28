#
#  ISC License
#
#  Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
#
#  Permission to use, copy, modify, and/or distribute this software for any
#  purpose with or without fee is hereby granted, provided that the above
#  copyright notice and this permission notice appear in all copies.
#
#  THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
#  WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
#  ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
#  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
#  ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
#  OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#

"""
PEP 517 build backend for bsk-sdk.

Wraps scikit-build-core and enforces that vendored Basilisk artifacts
(headers, runtime sources, SWIG files) are present before the build begins.
Set ``BSK_SDK_AUTO_SYNC=1`` to trigger an automatic sync during build.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


from scikit_build_core import build as _backend


def _truthy(value: str | None, default: bool = False) -> bool:
    """Return True when value looks like an affirmative flag (``1``, ``true``, ``yes``, ``on``)."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _required_sync_paths(repo_root: Path) -> list[Path]:
    """Return the directories that must exist and be non-empty before a build can proceed."""
    sdk_src = repo_root / "src" / "bsk_sdk"
    return [
        sdk_src / "include" / "Basilisk",
        sdk_src / "arch_min",
        sdk_src / "runtime_min",
        sdk_src / "swig",
    ]


def _has_any_file(path: Path) -> bool:
    """Return True if path is a directory containing at least one regular file."""
    if not path.exists() or not path.is_dir():
        return False
    return any(child.is_file() for child in path.rglob("*"))


def _assert_synced_artifacts(repo_root: Path) -> None:
    """Raise :class:`RuntimeError` if any required sync artifact directories are missing or empty."""
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
    """Execute ``tools/sync_all.py`` to pull vendored Basilisk artifacts from the submodule."""
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
    """Optionally run sync (if ``BSK_SDK_AUTO_SYNC=1``), then assert artifacts are present."""
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
    """Build a wheel, ensuring vendored artifacts are present first."""
    _prepare_artifacts()
    return _backend.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_editable(
    wheel_directory: str,
    config_settings: dict[str, str] | None = None,
    metadata_directory: str | None = None,
) -> str:
    """Build an editable wheel, ensuring vendored artifacts are present first."""
    _prepare_artifacts()
    return _backend.build_editable(wheel_directory, config_settings, metadata_directory)


def build_sdist(
    sdist_directory: str,
    config_settings: dict[str, str] | None = None,
) -> str:
    """Build a source distribution, ensuring vendored artifacts are present first."""
    _prepare_artifacts()
    return _backend.build_sdist(sdist_directory, config_settings)


def get_requires_for_build_wheel(
    config_settings: dict[str, str] | None = None,
) -> list[str]:
    """Return build-time dependencies required for wheel builds."""
    return _backend.get_requires_for_build_wheel(config_settings)


def get_requires_for_build_editable(
    config_settings: dict[str, str] | None = None,
) -> list[str]:
    """Return build-time dependencies required for editable installs."""
    return _backend.get_requires_for_build_editable(config_settings)


def get_requires_for_build_sdist(
    config_settings: dict[str, str] | None = None,
) -> list[str]:
    """Return build-time dependencies required for sdist builds."""
    return _backend.get_requires_for_build_sdist(config_settings)


def prepare_metadata_for_build_wheel(
    metadata_directory: str,
    config_settings: dict[str, str] | None = None,
) -> str:
    """Generate wheel metadata without performing a full build."""
    return _backend.prepare_metadata_for_build_wheel(
        metadata_directory, config_settings
    )


def prepare_metadata_for_build_editable(
    metadata_directory: str,
    config_settings: dict[str, str] | None = None,
) -> str:
    """Generate editable-install metadata without performing a full build."""
    return _backend.prepare_metadata_for_build_editable(
        metadata_directory, config_settings
    )
