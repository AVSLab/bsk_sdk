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


def test_key_headers_present() -> None:
    include_root = Path(bsk_sdk.include_dir()) / "Basilisk"
    expected = [
        "architecture/_GeneralModuleFiles/sys_model.h",
        "architecture/messaging/messaging.h",
        "architecture/utilities/linearAlgebra.h",
        "architecture/utilities/gauss_markov.h",
        "simulation/dynamics/_GeneralModuleFiles/dynamicEffector.h",
        "simulation/dynamics/_GeneralModuleFiles/dynamicObject.h",
    ]
    for rel in expected:
        p = include_root / rel
        assert p.exists(), f"Expected header missing from SDK: {p}"
