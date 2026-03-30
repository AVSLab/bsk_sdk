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

and also syncs the message auto-source tools from the Basilisk repo into:

    sdk/tools/msgAutoSource/

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
SDK_MSG_AUTOSOURCE_ROOT = SDK_REPO_ROOT / "tools" / "msgAutoSource"

# msgAutoSource directory in BSK, relative to basilisk root.
BSK_MSG_AUTOSOURCE = "src/architecture/messaging/msgAutoSource"


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
    arch_src = basilisk_root / "src" / "architecture"

    SDK_SWIG_ROOT.mkdir(parents=True, exist_ok=True)

    # Auto-discover all .i and .swg files under architecture/_GeneralModuleFiles
    # and architecture/utilities, mirroring the structure under swig/.
    swig_src_dirs = [
        arch_src / "_GeneralModuleFiles",
        arch_src / "utilities",
    ]

    copied: list[Path] = []
    for src_dir in swig_src_dirs:
        for src in sorted(src_dir.glob("*.i")) + sorted(src_dir.glob("*.swg")):
            rel_under_swig = Path("architecture") / src_dir.name / src.name
            dst = SDK_SWIG_ROOT / rel_under_swig
            print(f"[bsk-sdk] Copying {src} -> {dst}")
            copy_file(src, dst)
            copied.append(dst)

    print(f"[bsk-sdk] SWIG synchronization complete ({len(copied)} files).")

    # Sync msgAutoSource tools from BSK
    bsk_msg_auto = basilisk_root / BSK_MSG_AUTOSOURCE
    if not bsk_msg_auto.is_dir():
        raise FileNotFoundError(
            f"[bsk-sdk] Missing msgAutoSource directory:\n  {bsk_msg_auto}"
        )

    SDK_MSG_AUTOSOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    msg_copied = 0
    for src_file in sorted(bsk_msg_auto.iterdir()):
        if not src_file.is_file():
            continue
        dst = SDK_MSG_AUTOSOURCE_ROOT / src_file.name
        print(f"[bsk-sdk] Copying {src_file} -> {dst}")
        shutil.copy2(src_file, dst)
        msg_copied += 1

    print(f"[bsk-sdk] msgAutoSource synchronization complete ({msg_copied} files).")


if __name__ == "__main__":
    main()
