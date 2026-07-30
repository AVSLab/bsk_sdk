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

"""Tests for the self-contained compatibility guard embedded in extensions."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import bsk_sdk
import pytest


def _guard_namespace(expected_version: str = "2.12.0") -> dict[str, object]:
    """Render the installed template with deterministic compatibility values."""
    template = (
        Path(bsk_sdk.cmake_config_dir()) / "bsk_extension_compatibility.py.in"
    )
    if not template.is_file():
        template = Path(__file__).resolve().parents[1] / "cmake" / template.name
    contents = template.read_text(encoding="utf-8")
    contents = contents.replace(
        "@BSK_EXTENSION_COMPATIBILITY_VERSION@", expected_version
    )
    contents = contents.replace("@BSK_EXTENSION_ABI_VERSION@", "7")
    contents = contents.replace("@BSK_EXTENSION_COMPATIBILITY_NAME@", "test_extension")
    namespace: dict[str, object] = {}
    exec(compile(contents, str(template), "exec"), namespace)
    return namespace


def _basilisk(version: str, abi_version: int) -> SimpleNamespace:
    """Return a minimal Basilisk module replacement for one guard invocation."""
    return SimpleNamespace(
        __version__=version,
        getBuildInfo=lambda: {
            "artifact": {"extensionAbiVersion": abi_version},
        },
    )


def test_compatibility_guard_accepts_matching_runtime(monkeypatch) -> None:
    """An extension loads when both the exact BSK version and ABI match."""
    monkeypatch.setitem(sys.modules, "Basilisk", _basilisk("2.12.0", 7))

    _guard_namespace()["check_basilisk_compatibility"]()


def test_compatibility_guard_rejects_version_mismatch(monkeypatch) -> None:
    """A patch-level mismatch fails before any native wrapper is imported."""
    monkeypatch.setitem(sys.modules, "Basilisk", _basilisk("2.12.1", 7))

    with pytest.raises(
        ImportError,
        match=(
            r"test_extension was built for Basilisk 2\.12\.0.*2\.12\.1.*"
            r"pip install.*bsk==2\.12\.0"
        ),
    ):
        _guard_namespace()["check_basilisk_compatibility"]()


def test_beta_compatibility_guard_uses_general_guidance(monkeypatch) -> None:
    """A beta mismatch avoids assuming a package index or Git branch."""
    monkeypatch.setitem(sys.modules, "Basilisk", _basilisk("2.12.0b1", 7))

    with pytest.raises(ImportError) as error:
        _guard_namespace("2.12.0b0")["check_basilisk_compatibility"]()

    message = str(error.value)
    assert "matching Basilisk and bsk-sdk sources or wheels" in message
    assert "pip install" not in message
    assert "git checkout" not in message


def test_compatibility_guard_rejects_abi_mismatch(monkeypatch) -> None:
    """A matching version cannot conceal an incompatible extension ABI."""
    monkeypatch.setitem(sys.modules, "Basilisk", _basilisk("2.12.0", 8))

    with pytest.raises(ImportError, match=r"extension ABI 7.*provides ABI 8"):
        _guard_namespace()["check_basilisk_compatibility"]()


def test_compatibility_guard_reports_missing_basilisk(monkeypatch) -> None:
    """A missing BSK installation produces an actionable import error."""
    monkeypatch.setitem(sys.modules, "Basilisk", None)

    with pytest.raises(ImportError, match=r"requires Basilisk 2\.12\.0"):
        _guard_namespace()["check_basilisk_compatibility"]()


def test_cmake_helper_generates_version_and_abi_guard(tmp_path: Path) -> None:
    """The public CMake helper embeds synchronized SDK compatibility values."""
    cmake = shutil.which("cmake")
    assert cmake is not None, "cmake must be available to test the installed helper"
    config_dir = Path(bsk_sdk.cmake_config_dir())
    helper = config_dir / "bsk_extension_compatibility.cmake"
    include_dir = Path(bsk_sdk.include_dir())
    if not helper.is_file():
        repository_root = Path(__file__).resolve().parents[1]
        helper = repository_root / "cmake" / helper.name
        include_dir = repository_root / "src" / "bsk_sdk" / "include"
    output_dir = tmp_path / "package"
    script = tmp_path / "generate_guard.cmake"
    script.write_text(
        "\n".join(
            [
                'set(BSK_SDK_BSK_VERSION "2.12.0")',
                f'set(BSK_SDK_INCLUDE_DIR "{include_dir.as_posix()}")',
                f'include("{helper.as_posix()}")',
                "bsk_add_extension_compatibility_guard(",
                '  EXTENSION_NAME "test_extension"',
                f'  OUTPUT_DIR "{output_dir.as_posix()}"',
                ")",
                "",
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run([cmake, "-P", str(script)], check=True)

    guard = (output_dir / "_bsk_compatibility.py").read_text(encoding="utf-8")
    assert 'EXPECTED_BSK_VERSION = "2.12.0"' in guard
    assert "EXPECTED_EXTENSION_ABI = 1" in guard
    assert 'EXTENSION_NAME = "test_extension"' in guard


def test_cmake_helper_requires_exact_prerelease_version(tmp_path: Path) -> None:
    """A pre-release SDK accepts only its exact Basilisk version."""
    cmake = shutil.which("cmake")
    assert cmake is not None, "cmake must be available to test the installed helper"
    helper = Path(bsk_sdk.cmake_config_dir()) / "bsk_extension_compatibility.cmake"
    if not helper.is_file():
        helper = Path(__file__).resolve().parents[1] / "cmake" / helper.name
    script = tmp_path / "reject_version_mismatch.cmake"
    script.write_text(
        "\n".join(
            [
                f'include("{helper.as_posix()}")',
                '_bsk_sdk_require_exact_basilisk_version("2.12.0b0" "2.12.0b0")',
                '_bsk_sdk_require_exact_basilisk_version("2.12.0" "2.12.0b0")',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [cmake, "-P", str(script)], capture_output=True, text=True, check=False
    )

    assert result.returncode != 0
    assert "bsk-sdk was synced from Basilisk 2.12.0b0" in result.stderr
    assert "Installed Basilisk is 2.12.0" in result.stderr
    normalized_error = " ".join(result.stderr.split())
    assert "matching Basilisk and bsk-sdk sources or wheels" in normalized_error
    assert "pip install" not in result.stderr
    assert "git checkout" not in result.stderr
