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
Synchronize Basilisk base-class sources into the SDK package.

Auto-discovers all .cpp files under ``_GeneralModuleFiles/`` in ``fswAlgorithms/``
and ``simulation/`` (excluding directories with external dependencies like
``mujocoDynamics/``) and copies them into:

    sdk/src/bsk_sdk/runtime_min/

Also auto-generates "flat include" compatibility shims into:

    sdk/src/bsk_sdk/include_compat/

so runtime_min translation units that use flat includes like
``#include "atmosphereBase.h"`` compile without patching upstream sources.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _sync_paths import SDK_REPO_ROOT, resolve_basilisk_src_root

SDK_RUNTIME_ROOT = SDK_REPO_ROOT / "src" / "bsk_sdk" / "runtime_min"
SDK_INCLUDE_ROOT = SDK_REPO_ROOT / "src" / "bsk_sdk" / "include" / "Basilisk"
SDK_COMPAT_INCLUDE_ROOT = SDK_REPO_ROOT / "src" / "bsk_sdk" / "include_compat"

# Top-level source dirs to scan for _GeneralModuleFiles/*.cpp.
RUNTIME_TOP_DIRS: list[str] = ["fswAlgorithms", "simulation"]

# Subdirectories to skip (e.g. external dependencies like MuJoCo).
SKIP_SUBDIRS: set[str] = {"mujocoDynamics"}

# Matches #include "Header.h"
INCLUDE_RE = re.compile(r'^\s*#\s*include\s*"([^"]+)"\s*$')


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


_SYSTEM_HEADERS: set[str] = {
    "string.h", "stdlib.h", "stdio.h", "math.h", "stdint.h", "stddef.h",
    "ctype.h", "assert.h", "errno.h", "float.h", "limits.h", "signal.h",
    "time.h", "stdbool.h", "inttypes.h",
}


def _is_flat_header(h: str) -> bool:
    return "/" not in h and "\\" not in h and h.endswith((".h", ".hpp")) and h not in _SYSTEM_HEADERS


def _find_header_under_sdk(include_root: Path, header_name: str) -> Path | None:
    """
    Find a header by basename under include_root.
    """
    matches = list(include_root.rglob(header_name))
    if not matches:
        return None
    if len(matches) > 1:
        raise RuntimeError(
            f"Ambiguous header '{header_name}' found in multiple locations:\n"
            + "\n".join(f"  - {m}" for m in matches)
        )
    return matches[0]


def _header_rel_to_basilisk(include_root: Path, header_path: Path) -> str:
    return header_path.relative_to(include_root).as_posix()


def generate_compat_shims_for_runtime() -> None:
    if not SDK_INCLUDE_ROOT.exists():
        raise RuntimeError(
            f"SDK headers root does not exist: {SDK_INCLUDE_ROOT}\n"
            "Did you run sync_headers.py first (or otherwise populate sdk/src/bsk_sdk/include/Basilisk)?"
        )

    SDK_COMPAT_INCLUDE_ROOT.mkdir(parents=True, exist_ok=True)

    runtime_cpp_files = sorted(SDK_RUNTIME_ROOT.glob("*.cpp"))
    needed_flat_headers: set[str] = set()

    for cpp in runtime_cpp_files:
        text = cpp.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            m = INCLUDE_RE.match(line)
            if not m:
                continue
            hdr = m.group(1)
            if _is_flat_header(hdr):
                needed_flat_headers.add(hdr)

    for hdr in sorted(needed_flat_headers):
        real = _find_header_under_sdk(SDK_INCLUDE_ROOT, hdr)
        if real is None:
            raise FileNotFoundError(
                f"runtime_min needs '{hdr}' but it was not found under SDK headers:\n"
                f"  {SDK_INCLUDE_ROOT}\n"
                "Fix sync_headers.py DIRECTORIES to include the missing header."
            )
        rel = _header_rel_to_basilisk(SDK_INCLUDE_ROOT, real)

        shim = SDK_COMPAT_INCLUDE_ROOT / hdr
        shim.write_text(f'#pragma once\n#include "{rel}"\n', encoding="utf-8")
        print(f"[bsk-sdk] compat shim: {shim} -> {rel}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Sync Basilisk runtime_min sources into bsk-sdk"
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

    SDK_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)

    for top in RUNTIME_TOP_DIRS:
        top_dir = src_root / top
        if not top_dir.exists():
            continue
        for gmf in sorted(top_dir.rglob("_GeneralModuleFiles")):
            if not gmf.is_dir():
                continue
            if any(part in SKIP_SUBDIRS for part in gmf.relative_to(src_root).parts):
                continue
            for cpp in sorted(gmf.glob("*.cpp")):
                dst = SDK_RUNTIME_ROOT / cpp.name
                print(f"[bsk-sdk] Copying {cpp} -> {dst}")
                copy_file(cpp, dst)

    generate_compat_shims_for_runtime()
    print("[bsk-sdk] Runtime synchronization complete.")


if __name__ == "__main__":
    main()
