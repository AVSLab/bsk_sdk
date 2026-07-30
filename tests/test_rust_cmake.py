# ISC License
#
# Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""Tests for the installed SDK Rust CMake integration."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import bsk_sdk


def _rust_cmake_paths() -> tuple[Path, Path]:
    """Return installed helpers, with a source-tree fallback for local tests."""
    helper = Path(bsk_sdk.cmake_config_dir()) / "bsk_add_rust_module.cmake"
    rust_cmake = Path(bsk_sdk.rust_dir()) / "cmake"
    if helper.is_file():
        return helper, rust_cmake

    repository_root = Path(__file__).resolve().parents[1]
    return repository_root / "cmake" / helper.name, rust_cmake


def test_shared_windows_export_contract(tmp_path: Path) -> None:
    """The shared Windows ABI file stays in the organized Rust build tree."""
    cmake = shutil.which("cmake")
    assert cmake is not None, "cmake must be available to test the installed helper"
    _, rust_cmake = _rust_cmake_paths()
    shared_helper = rust_cmake / "bskAddRustModuleSources.cmake"
    expected = [
        "Create_example",
        "Config_example",
        "GetConfigField_example",
        "SetConfigField_example",
        "ConfigFieldDeprecationDate_example",
        "ConfigFieldDeprecationMessage_example",
        "ModuleDeprecationDate_example",
        "ModuleDeprecationMessage_example",
        "Destroy_example",
        "SelfInit_example",
        "Reset_example",
        "Update_example",
        "BskRustError_kind",
        "BskRustError_message",
        "Destroy_BskRustError",
    ]
    source_dir = tmp_path / "source"
    build_dir = tmp_path / "build"
    source_dir.mkdir()
    (source_dir / "example.c").write_text("void example(void) {}\n", encoding="utf-8")
    (source_dir / "CMakeLists.txt").write_text(
        "\n".join(
            [
                "cmake_minimum_required(VERSION 3.26)",
                "project(test_rust_exports LANGUAGES C)",
                "set(WIN32 TRUE)",
                f'include("{shared_helper.as_posix()}")',
                'add_library(example MODULE "example.c")',
                '_bsk_add_rust_windows_exports("example" "example")',
                "",
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [cmake, "-S", str(source_dir), "-B", str(build_dir)], check=True
    )

    export_file = build_dir / "rust" / "exports" / "example.def"
    assert export_file.is_file()
    assert not (build_dir / "rust_exports").exists()
    assert export_file.read_text(encoding="utf-8").splitlines() == [
        "EXPORTS",
        *(f"    {symbol}" for symbol in expected),
    ]


def test_workspace_metadata_discovers_multiple_rust_modules(tmp_path: Path) -> None:
    """Every marked static-library package is returned in workspace order."""
    cmake = shutil.which("cmake")
    assert cmake is not None, "cmake must be available to test the installed helper"
    support_version = bsk_sdk.rust_support_crate_version()
    exact_support_version = f"={support_version}"

    metadata = {
        "packages": [
            {
                "metadata": {"basilisk": {"module": True}},
                "manifest_path": "/workspace/first/Cargo.toml",
                "dependencies": [
                    {"name": "bsk-build", "req": exact_support_version},
                    {"name": "bsk-messages", "req": exact_support_version},
                ],
                "targets": [{"name": "first", "crate_types": ["staticlib"]}],
            },
            {
                "metadata": {"basilisk": {"module": False}},
                "manifest_path": "/workspace/support/Cargo.toml",
                "dependencies": [],
                "targets": [{"name": "support", "crate_types": ["lib"]}],
            },
            {
                "metadata": {"basilisk": {"module": True}},
                "manifest_path": "/workspace/second/Cargo.toml",
                "dependencies": [
                    {"name": "bsk-build", "req": exact_support_version},
                    {"name": "bsk-messages", "req": exact_support_version},
                ],
                "targets": [{"name": "second", "crate_types": ["staticlib"]}],
            },
        ]
    }
    helper, rust_cmake = _rust_cmake_paths()
    script = tmp_path / "test_multiple_rust_modules.cmake"
    script.write_text(
        "\n".join(
            [
                f'set(BSK_SDK_RUST_CMAKE_DIR "{rust_cmake.as_posix()}")',
                f'include("{helper.as_posix()}")',
                "_bsk_sdk_rust_modules_from_metadata(",
                f"  [==[{json.dumps(metadata)}]==] _targets _manifests)",
                'if(NOT "${_targets}" STREQUAL "first;second")',
                '  message(FATAL_ERROR "unexpected targets: ${_targets}")',
                "endif()",
                'if(NOT "${_manifests}" STREQUAL '
                '"/workspace/first/Cargo.toml;/workspace/second/Cargo.toml")',
                '  message(FATAL_ERROR "unexpected manifests: ${_manifests}")',
                "endif()",
                "",
            ]
        ),
        encoding="utf-8",
    )

    empty_path = tmp_path / "no-rust-tools"
    empty_path.mkdir()
    environment = os.environ.copy()
    environment["PATH"] = str(empty_path)
    subprocess.run([cmake, "-P", str(script)], check=True, env=environment)


def test_workspace_metadata_watches_every_package_manifest(tmp_path: Path) -> None:
    """Changing any workspace package manifest triggers CMake reconfiguration."""
    cmake = shutil.which("cmake")
    assert cmake is not None, "cmake must be available to test the installed helper"
    helper, rust_cmake = _rust_cmake_paths()
    workspace_manifest = tmp_path / "workspace" / "Cargo.toml"
    lockfile = workspace_manifest.with_name("Cargo.lock")
    module_manifest = tmp_path / "workspace" / "module" / "Cargo.toml"
    support_manifest = tmp_path / "workspace" / "support" / "Cargo.toml"
    metadata = {
        "packages": [
            {"manifest_path": str(module_manifest)},
            {"manifest_path": str(support_manifest)},
        ]
    }
    expected = [workspace_manifest, lockfile, module_manifest, support_manifest]
    script = tmp_path / "test_workspace_dependencies.cmake"
    script.write_text(
        "\n".join(
            [
                f'set(BSK_SDK_RUST_CMAKE_DIR "{rust_cmake.as_posix()}")',
                f'include("{helper.as_posix()}")',
                "_bsk_sdk_register_rust_metadata_dependencies(",
                f"  [==[{json.dumps(metadata)}]==] \"{workspace_manifest.as_posix()}\")",
                "get_property(_dependencies DIRECTORY PROPERTY CMAKE_CONFIGURE_DEPENDS)",
                *(
                    f'list(FIND _dependencies "{path.as_posix()}" _found_{index})\n'
                    f"if(_found_{index} EQUAL -1)\n"
                    f'  message(FATAL_ERROR "missing dependency: {path.as_posix()}")\n'
                    "endif()"
                    for index, path in enumerate(expected)
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run([cmake, "-P", str(script)], check=True)


def test_workspace_metadata_rejects_mismatched_support_crates(tmp_path: Path) -> None:
    """A module cannot silently combine SDK and support-crate release lines."""
    cmake = shutil.which("cmake")
    assert cmake is not None, "cmake must be available to test the installed helper"
    support_version = bsk_sdk.rust_support_crate_version()
    exact_support_version = f"={support_version}"
    metadata = {
        "packages": [
            {
                "metadata": {"basilisk": {"module": True}},
                "manifest_path": "/workspace/stale/Cargo.toml",
                "dependencies": [
                    {"name": "bsk-build", "req": "^0.1"},
                    {"name": "bsk-messages", "req": exact_support_version},
                ],
                "targets": [{"name": "stale", "crate_types": ["staticlib"]}],
            }
        ]
    }
    helper, rust_cmake = _rust_cmake_paths()
    script = tmp_path / "test_mismatched_rust_versions.cmake"
    script.write_text(
        "\n".join(
            [
                f'set(BSK_SDK_RUST_CMAKE_DIR "{rust_cmake.as_posix()}")',
                f'include("{helper.as_posix()}")',
                "_bsk_sdk_rust_modules_from_metadata(",
                f"  [==[{json.dumps(metadata)}]==] _targets _manifests)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [cmake, "-P", str(script)], capture_output=True, text=True, check=False
    )
    assert result.returncode != 0
    assert (
        f"bsk-build must use the exact version {exact_support_version}"
        in result.stderr
    )
