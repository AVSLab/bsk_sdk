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
Basilisk SDK (``bsk-sdk``) -- build Basilisk-compatible SWIG plugins out-of-tree.

This package ships curated Basilisk headers, minimal runtime sources,
SWIG interface files, and CMake helpers so that external projects can
compile and link Basilisk plugins without vendoring the full simulation
codebase.

Quick start::

    pip install bsk-sdk

Then in your plugin's ``CMakeLists.txt``::

    find_package(bsk-sdk CONFIG REQUIRED)
    bsk_add_swig_module(TARGET myPlugin INTERFACE swig/myPlugin.i ...)

Convenience functions below expose installed paths for headers, SWIG
support files, CMake config, and tools.
"""

from importlib import resources
from pathlib import Path


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
        str(root / "include" / "Basilisk"),
        str(root / "include" / "compat"),
    ]


def swig_dir() -> str:
    return str(package_root() / "swig")


def tools_dir() -> str:
    return str(package_root() / "tools")


def msg_autosource_dir() -> str:
    return str(package_root() / "tools" / "msgAutoSource")


__all__ = [
    "package_root",
    "bsk_version",
    "cmake_config_dir",
    "include_dir",
    "include_dirs",
    "swig_dir",
    "tools_dir",
    "msg_autosource_dir",
]
