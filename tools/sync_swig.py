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
Synchronize a curated subset of Basilisk SWIG support files into the SDK package.

Copies into:

    sdk/src/bsk_sdk/swig/...

So plugin builds can depend solely on the installed `bsk-sdk` package.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _sync_paths import SDK_REPO_ROOT, resolve_basilisk_root

SDK_SWIG_ROOT = SDK_REPO_ROOT / "src" / "bsk_sdk" / "swig"

SWIG_FILES: list[str] = [
    "src/architecture/_GeneralModuleFiles/swig_conly_data.i",
    "src/architecture/_GeneralModuleFiles/swig_std_array.i",
    "src/architecture/_GeneralModuleFiles/swig_eigen.i",
    "src/architecture/_GeneralModuleFiles/sys_model.i",
    "src/architecture/_GeneralModuleFiles/sys_model.h",
    "src/architecture/utilities/bskException.swg",
]


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Sync Basilisk SWIG support files into bsk-sdk"
    )
    ap.add_argument(
        "--basilisk-root",
        default=None,
        help="Path to Basilisk repository root (or set BSK_BASILISK_ROOT).",
    )
    args = ap.parse_args()

    basilisk_root = resolve_basilisk_root(args.basilisk_root)

    SDK_SWIG_ROOT.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    for rel in SWIG_FILES:
        src = basilisk_root / rel
        if not src.exists():
            raise FileNotFoundError(
                f"[bsk-sdk] Missing SWIG support file:\n  {src}\n\n"
                "Update sdk/tools/sync_swig.py (SWIG_FILES) to match repo layout."
            )

        rel_path = Path(rel)

        # Strip leading "src/" so SWIG includes like:
        #   %include "architecture/_GeneralModuleFiles/sys_model.i"
        # work when you pass -I${BSK_SDK_SWIG_DIR}
        if rel_path.parts and rel_path.parts[0] == "src":
            rel_under_swig = Path(*rel_path.parts[1:])
        else:
            rel_under_swig = rel_path.name

        dst = SDK_SWIG_ROOT / rel_under_swig
        print(f"[bsk-sdk] Copying {src} -> {dst}")
        copy_file(src, dst)
        copied.append(dst)

    print(f"[bsk-sdk] SWIG synchronization complete ({len(copied)} files).")


if __name__ == "__main__":
    main()
