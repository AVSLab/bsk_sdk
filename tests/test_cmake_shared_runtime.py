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

"""CMake integration coverage for the shared vendored SDK runtime."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import bsk_sdk


def test_sdk_runtime_is_built_once_and_reused(tmp_path: Path) -> None:
    cmake = shutil.which("cmake")
    assert cmake is not None, (
        "cmake must be available to test the installed CMake helper"
    )

    fixture_dir = Path(__file__).parent / "cmake" / "shared_runtime"
    build_dir = tmp_path / "build"
    subprocess.run(
        [
            cmake,
            "-S",
            str(fixture_dir),
            "-B",
            str(build_dir),
            f"-DBSK_SDK_CMAKE_DIR={bsk_sdk.cmake_config_dir()}",
        ],
        check=True,
    )
    subprocess.run(
        [cmake, "--build", str(build_dir)],
        check=True,
    )
