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
Synchronize Basilisk source files into the SDK package.

This complements sync_headers.py:

- sync_headers.py vendors public headers into:
    sdk/src/bsk_sdk/include/Basilisk/...

- sync_sources.py vendors core architecture sources ("arch_min") into:
    sdk/src/bsk_sdk/arch_min/...

- sync_sources.py vendors architecture utility sources into:
    sdk/src/bsk_sdk/arch_utilities/...

These files are compiled by the bsk-sdk CMake project so plugin authors do not
have to compile them in every plugin.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _sync_paths import SDK_REPO_ROOT, resolve_basilisk_src_root

SDK_ARCH_MIN_ROOT = SDK_REPO_ROOT / "src" / "bsk_sdk" / "arch_min"
SDK_ARCH_UTILITIES_ROOT = SDK_REPO_ROOT / "src" / "bsk_sdk" / "arch_utilities"

ARCH_MIN_FILES: list[tuple[str, str]] = [
    ("architecture/_GeneralModuleFiles/sys_model.cpp", "sys_model.cpp"),
    (
        "architecture/utilities/moduleIdGenerator/moduleIdGenerator.cpp",
        "moduleIdGenerator.cpp",
    ),
]

UTILITY_SOURCE_SUFFIXES = {".c", ".cpp"}
EXCLUDED_UTILITY_SOURCES = {
    # Depends on cfitsio/fitsio.h. Keep the SDK self-contained.
    "haslamBackgroundRadiation.cpp",
}


def copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Sync Basilisk arch_min sources into bsk-sdk"
    )
    ap.add_argument(
        "--basilisk-root",
        default=None,
        help="Path to Basilisk repository root (or set BSK_BASILISK_ROOT).",
    )
    args = ap.parse_args()

    src_root = resolve_basilisk_src_root(args.basilisk_root)

    if not src_root.exists():
        raise RuntimeError(f"Expected Basilisk src directory not found: {src_root}")

    reset_dir(SDK_ARCH_MIN_ROOT)
    reset_dir(SDK_ARCH_UTILITIES_ROOT)

    copied: list[Path] = []
    for rel_src, out_name in ARCH_MIN_FILES:
        src_file = src_root / rel_src
        if not src_file.exists():
            raise FileNotFoundError(f"Missing source file: {src_file}")

        dest_file = SDK_ARCH_MIN_ROOT / out_name
        print(f"[bsk-sdk] Copying {src_file} -> {dest_file}")
        copy_file(src_file, dest_file)
        copied.append(dest_file)

    utilities_dir = src_root / "architecture" / "utilities"
    if not utilities_dir.exists():
        raise FileNotFoundError(f"Missing utilities directory: {utilities_dir}")

    for src_file in sorted(utilities_dir.iterdir()):
        if not src_file.is_file() or src_file.suffix not in UTILITY_SOURCE_SUFFIXES:
            continue
        if src_file.name in EXCLUDED_UTILITY_SOURCES:
            print(f"[bsk-sdk] Skipping {src_file} (external dependency)")
            continue

        dest_file = SDK_ARCH_UTILITIES_ROOT / src_file.name
        print(f"[bsk-sdk] Copying {src_file} -> {dest_file}")
        copy_file(src_file, dest_file)
        copied.append(dest_file)

    print(f"[bsk-sdk] Source synchronization complete ({len(copied)} files).")


if __name__ == "__main__":
    main()
