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
Basilisk SDK (``bsk-sdk``) -- build Basilisk-compatible SWIG extensions out-of-tree.

This package ships curated Basilisk headers, minimal runtime sources,
SWIG interface files, and CMake helpers so that external projects can
compile and link Basilisk extensions without vendoring the full simulation
codebase.

Quick start::

    pip install bsk-sdk

Then in your extension's ``CMakeLists.txt``::

    find_package(bsk-sdk CONFIG REQUIRED)
    bsk_add_swig_module(TARGET myExtension INTERFACE swig/myExtension.i ...)

Convenience functions below expose installed paths for headers, SWIG
support files, CMake config, and tools.
"""

import json
from importlib import resources
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

try:
    __version__ = version("bsk-sdk")
except PackageNotFoundError:
    __version__ = "unknown"


def package_root() -> Path:
    return Path(resources.files(__package__))


def bsk_version() -> str:
    """Return the Basilisk version this SDK was synced from."""
    return (package_root() / "_bsk_version.txt").read_text().strip()


def cmake_config_dir() -> str:
    return str(package_root() / "lib" / "cmake" / "bsk-sdk")


def include_dir() -> str:
    return str(package_root() / "include")


def include_dirs() -> list[str]:
    root = package_root()
    return [
        str(root / "include"),
        str(root / "include" / "cMsgCInterface"),
        str(root / "include" / "Basilisk"),
        str(root / "include" / "compat"),
    ]


def c_msg_interface_dir() -> str:
    return str(package_root() / "include" / "cMsgCInterface")


def swig_dir() -> str:
    return str(package_root() / "swig")


def tools_dir() -> str:
    return str(package_root() / "tools")


def rust_dir() -> str:
    """Return the installed SDK directory containing Rust build support."""
    return str(package_root() / "rust")


def rust_support_versions() -> dict[str, str]:
    """Return synchronized Rust, support-crate, and Corrosion versions."""
    metadata = Path(rust_dir()) / "support-versions.json"
    return json.loads(metadata.read_text(encoding="utf-8"))


def rust_minimum_version() -> str:
    """Return the minimum Rust compiler version supported by this SDK."""
    return rust_support_versions()["BSK_RUST_MIN_VERSION"]


def rust_support_crate_version() -> str:
    """Return the exact ``bsk-*`` support-crate version required by this SDK."""
    return rust_support_versions()["BSK_RUST_SUPPORT_CRATE_VERSION"]


def rust_license_tool_version() -> str:
    """Return the exact ``cargo-about`` version used for Rust license reports."""
    return rust_support_versions()["BSK_CARGO_ABOUT_VERSION"]


def rust_license_generator() -> str:
    """Return the reusable Rust third-party license generator path."""
    return str(Path(rust_dir()) / "licenses" / "generate_rust_licenses.py")


def rust_license_config() -> str:
    """Return the SDK's default ``cargo-about`` policy path."""
    return str(Path(rust_dir()) / "licenses" / "about.toml")


def rust_libclang_dir() -> str:
    """Return the bundled ``libclang`` directory used on Linux and Windows."""
    try:
        import clang
    except ImportError as error:
        raise RuntimeError(
            "The libclang Python package required by bsk-sdk is not installed"
        ) from error

    directory = Path(clang.__file__).resolve().parent / "native"
    if not directory.is_dir():
        raise RuntimeError(
            f"The libclang Python package has no native library directory: {directory}"
        )
    return str(directory)


def msg_autosource_dir() -> str:
    return str(package_root() / "tools" / "msgAutoSource")


__all__ = [
    "__version__",
    "package_root",
    "bsk_version",
    "cmake_config_dir",
    "include_dir",
    "include_dirs",
    "c_msg_interface_dir",
    "swig_dir",
    "tools_dir",
    "rust_dir",
    "rust_support_versions",
    "rust_minimum_version",
    "rust_support_crate_version",
    "rust_license_tool_version",
    "rust_license_generator",
    "rust_license_config",
    "rust_libclang_dir",
    "msg_autosource_dir",
]
