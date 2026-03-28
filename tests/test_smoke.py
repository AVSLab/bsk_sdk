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
Smoke tests for the installed bsk-sdk wheel.

Verifies that the package is importable, all advertised paths exist on disk,
and the CMake config directory contains the expected files.
"""

from __future__ import annotations

from pathlib import Path

import bsk_sdk


def test_package_root_exists() -> None:
    root = bsk_sdk.package_root()
    assert Path(root).is_dir(), f"package_root() does not exist: {root}"


def test_include_dirs_exist() -> None:
    for d in bsk_sdk.include_dirs():
        assert Path(d).is_dir(), f"include dir missing: {d}"


def test_swig_dir_exists() -> None:
    assert Path(bsk_sdk.swig_dir()).is_dir()


def test_tools_dir_exists() -> None:
    assert Path(bsk_sdk.tools_dir()).is_dir()


def test_cmake_config_dir_exists() -> None:
    assert Path(bsk_sdk.cmake_config_dir()).is_dir()


def test_cmake_config_files_present() -> None:
    config_dir = Path(bsk_sdk.cmake_config_dir())
    assert (config_dir / "bsk-sdkConfig.cmake").exists()
    assert (config_dir / "bsk-sdkConfigVersion.cmake").exists()
    assert (config_dir / "bsk-sdkTargets.cmake").exists()
