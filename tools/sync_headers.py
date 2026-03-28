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
Synchronize a curated subset of Basilisk headers into the SDK package.

Copies selected directories from the main Basilisk `src/` tree into:

    sdk/src/bsk_sdk/include/Basilisk/

Only the headers that plugin authors need to compile against are included.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _sync_paths import SDK_REPO_ROOT, resolve_basilisk_src_root

SDK_INCLUDE_ROOT = SDK_REPO_ROOT / "src" / "bsk_sdk" / "include" / "Basilisk"

# Top-level directories to vendor into the SDK, relative to src/.
DIRECTORIES = [
    "architecture",
    "fswAlgorithms/fswUtilities",
    # reactionWheels is referenced by auto-generated SWIG interfaces; not a
    # _GeneralModuleFiles dir so it must be listed explicitly until upstream
    # BSK restructures it.
    "simulation/dynamics/reactionWheels",
    # Note general module files are handled separately below
]


def _discover_general_module_dirs(src_root: Path) -> list[str]:
    """Auto-discover ``_GeneralModuleFiles`` directories under fswAlgorithms/ and simulation/."""
    found: list[str] = []
    for top in ("fswAlgorithms", "simulation"):
        top_dir = src_root / top
        if not top_dir.exists():
            continue
        for gmf in sorted(top_dir.rglob("_GeneralModuleFiles")):
            if gmf.is_dir():
                found.append(str(gmf.relative_to(src_root)))
    return found


# Things that must be excluded from the SDK
IGNORE_PATTERNS = [
    "_UnitTest",
    "_Documentation",
    "__pycache__",
    "*.swg",
    "*.i",
    "*.py",
    "*.cpp",
    "*.c",
]


def copy_tree(src: Path, dest: Path) -> None:
    """Replace dest with a filtered copy of src."""
    if dest.exists():
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)

    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns(*IGNORE_PATTERNS),
    )


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Sync Basilisk public headers into bsk-sdk/src/bsk_sdk/include/Basilisk"
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

    SDK_INCLUDE_ROOT.mkdir(parents=True, exist_ok=True)

    all_dirs = list(DIRECTORIES) + _discover_general_module_dirs(src_root)

    for relative in all_dirs:
        src_dir = src_root / relative
        dest_dir = SDK_INCLUDE_ROOT / relative

        if not src_dir.exists():
            raise FileNotFoundError(f"Missing source directory: {src_dir}")

        print(f"[bsk-sdk] Copying {src_dir} -> {dest_dir}")
        copy_tree(src_dir, dest_dir)

    print("[bsk-sdk] Header synchronization complete.")


if __name__ == "__main__":
    main()
