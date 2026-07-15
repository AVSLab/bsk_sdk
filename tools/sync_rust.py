#!/usr/bin/env python3

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
Copy the ``bsk_add_rust_module_sources`` CMake macro from the Basilisk
repository into the SDK package -- see ``src/cmake/bskAddRustModuleSources.cmake``
in Basilisk.

Copies into:

    sdk/cmake/bskAddRustModuleSources.cmake

The Rust crates a plugin's ``Cargo.toml`` depends on (``bsk-build``,
``bsk-messages``, ``bsk-utilities``) are *not* vendored here. They aren't
published to crates.io yet, so plugin authors depend on them directly from
the Basilisk repository via a Cargo ``git`` dependency instead -- see
"Writing a Rust Plugin" in the Basilisk documentation. This keeps the only
thing bsk-sdk needs to copy for Rust support to the CMake macro, which Cargo
has no way to fetch on its own.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from _sync_paths import SDK_REPO_ROOT, resolve_basilisk_root
from common import copy_file  # noqa: E402

SDK_CMAKE_ROOT = SDK_REPO_ROOT / "cmake"

# (path relative to Basilisk root, path relative to SDK_CMAKE_ROOT)
CMAKE_FILES: list[tuple[str, str]] = [
    ("src/cmake/bskAddRustModuleSources.cmake", "bskAddRustModuleSources.cmake"),
]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Copy the Basilisk-core Rust module CMake macro into bsk-sdk"
    )
    ap.add_argument(
        "--basilisk-root",
        default=None,
        help="Path to Basilisk repository root (or set BSK_BASILISK_ROOT).",
    )
    args = ap.parse_args()

    basilisk_root = resolve_basilisk_root(args.basilisk_root)

    for rel_src, rel_dst in CMAKE_FILES:
        src_file = basilisk_root / rel_src
        if not src_file.exists():
            raise FileNotFoundError(f"Missing CMake file: {src_file}")
        dst_file = SDK_CMAKE_ROOT / rel_dst
        print(f"[bsk-sdk] Copying {src_file} -> {dst_file}")
        copy_file(src_file, dst_file)

    print("[bsk-sdk] Rust tooling copy complete.")


if __name__ == "__main__":
    main()
