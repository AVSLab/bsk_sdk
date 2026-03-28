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


from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _sync_paths import resolve_basilisk_root


def run(cmd: list[str], cwd: Path) -> None:
    print(f"\n==> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


BSK_VERSION_FILE = "docs/source/bskVersion.txt"


def stamp_bsk_version(bsk_root: Path, repo_root: Path) -> None:
    """Read bskVersion.txt from Basilisk and write it into the SDK package."""
    version_file = bsk_root / BSK_VERSION_FILE
    if not version_file.exists():
        raise FileNotFoundError(
            f"Basilisk version file not found: {version_file}\n"
            "Is the Basilisk root correct?"
        )
    bsk_version = version_file.read_text().strip()
    dst = repo_root / "src" / "bsk_sdk" / "_bsk_version.txt"
    dst.write_text(bsk_version + "\n")
    print(f"\n[bsk-sdk] Stamped BSK version: {bsk_version} -> {dst}")


def sync_basilisk_submodule(repo_root: Path) -> None:
    run(
        [
            "git",
            "submodule",
            "update",
            "--init",
            "--recursive",
            "external/basilisk",
        ],
        cwd=repo_root,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Run all bsk-sdk sync scripts in order.")
    ap.add_argument(
        "--sdk-tools-dir",
        default=None,
        help="Path to sdk/tools (defaults to this script's directory).",
    )
    ap.add_argument(
        "--basilisk-root",
        default=None,
        help="Path to Basilisk repository root (or set BSK_BASILISK_ROOT).",
    )
    ap.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use (default: current interpreter).",
    )
    ap.add_argument(
        "--sync-submodules",
        action="store_true",
        help="Run 'git submodule update --init --recursive external/basilisk' first.",
    )
    args = ap.parse_args()

    tools_dir = (
        Path(args.sdk_tools_dir).resolve()
        if args.sdk_tools_dir
        else Path(__file__).resolve().parent
    )
    py = args.python
    basilisk_root = str(Path(args.basilisk_root).resolve()) if args.basilisk_root else None
    repo_root = tools_dir.parent

    if args.sync_submodules:
        sync_basilisk_submodule(repo_root)

    # Stamp BSK version from the resolved Basilisk source tree.
    bsk_root = resolve_basilisk_root(basilisk_root)
    stamp_bsk_version(bsk_root, repo_root)

    scripts = [
        "sync_headers.py",
        "sync_runtime.py",
        "sync_sources.py",
        "sync_swig.py",
    ]

    for s in scripts:
        p = tools_dir / s
        if not p.exists():
            raise FileNotFoundError(f"Missing {p}")
        cmd = [py, str(p)]
        if basilisk_root:
            cmd.extend(["--basilisk-root", basilisk_root])
        run(cmd, cwd=tools_dir)

    print("\nAll sync steps completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
