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

"""Compile extensions with bundled and parent-provided Eigen targets."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import bsk_sdk
import pytest


@pytest.mark.parametrize(
    ("target_kind", "matching"),
    [
        ("bundled", True),
        ("imported", True),
        ("imported", False),
        ("alias", True),
        ("alias", False),
        ("include_override", False),
    ],
)
def test_extension_checks_selected_eigen_headers(
    tmp_path: Path, target_kind: str, matching: bool,
) -> None:
    """Only Eigen 5.0.1 compiles, even when CMake metadata claims a match."""
    cmake = shutil.which("cmake")
    assert cmake is not None, "cmake must be available to test the installed helper"
    include_dir = Path(bsk_sdk.include_dir()) / "eigen3"
    if not matching:
        include_dir = tmp_path / "old eigen"
        (include_dir / "Eigen").mkdir(parents=True)
        (include_dir / "Eigen" / "Core").write_text(
            "#define EIGEN_WORLD_VERSION 3\n"
            "#define EIGEN_MAJOR_VERSION 4\n"
            "#define EIGEN_MINOR_VERSION 0\n",
            encoding="utf-8",
        )

    setup = ""
    if target_kind == "imported":
        setup = (
            "add_library(Eigen3::Eigen INTERFACE IMPORTED GLOBAL)\n"
            "set_target_properties(Eigen3::Eigen PROPERTIES\n"
            f'  INTERFACE_INCLUDE_DIRECTORIES "{include_dir.as_posix()}")\n'
        )
    elif target_kind == "alias":
        setup = (
            "add_library(parent_eigen INTERFACE)\n"
            "target_include_directories(parent_eigen INTERFACE\n"
            f'  "$<BUILD_INTERFACE:{include_dir.as_posix()}>")\n'
            "add_library(Eigen3::Eigen ALIAS parent_eigen)\n"
        )
    extra_includes = include_dir.as_posix() if target_kind == "include_override" else ""
    config_dir = Path(bsk_sdk.cmake_config_dir()).as_posix()
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.26)\n"
        "project(eigen_version_test LANGUAGES C CXX)\n"
        "set(CMAKE_CXX_STANDARD 17)\n"
        + setup
        + 'set(Eigen3_VERSION "5.0.1")\n'
        + f'find_package(bsk-sdk CONFIG REQUIRED PATHS "{config_dir}" NO_DEFAULT_PATH)\n'
        + "find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)\n"
        + "add_library(extension_probe MODULE probe.cpp)\n"
        + '_bsk_configure_swig_target(extension_probe "${CMAKE_BINARY_DIR}/out"\n'
        + f'  "" "{extra_includes}")\n',
        encoding="utf-8",
    )
    (tmp_path / "probe.cpp").write_text(
        "int extension_probe() { return 0; }\n", encoding="utf-8",
    )
    build_dir = tmp_path / "build"
    subprocess.run(
        [
            cmake, "-S", str(tmp_path), "-B", str(build_dir),
            f"-DPython3_EXECUTABLE={sys.executable}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        [cmake, "--build", str(build_dir), "--config", "Release"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    if matching:
        assert result.returncode == 0, output
    else:
        assert result.returncode != 0, output
        assert "bsk-sdk requires Eigen 5.0.1" in output
