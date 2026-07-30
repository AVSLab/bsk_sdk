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
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _sync_paths import (
    BSK_BASILISK_ROOT_ENV,
    DEFAULT_BASILISK_SUBMODULE_DIR,
    resolve_basilisk_root,
)


def run(cmd: list[str], cwd: Path) -> None:
    print(f"\n==> {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=str(cwd), check=True)


BSK_VERSION_FILE = "docs/source/bskVersion.txt"
PROJECT_VERSION_RE = re.compile(r"^(\s*)version\s*=.*?(\r?\n?)$")


def update_pyproject_version(pyproject_path: Path, version: str) -> None:
    """Set ``[project].version`` in pyproject.toml to the synced BSK version."""
    lines = pyproject_path.read_text().splitlines(keepends=True)
    in_project = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue

        if in_project:
            match = PROJECT_VERSION_RE.match(line)
            if match:
                indent, newline = match.groups()
                lines[index] = f'{indent}version = "{version}"{newline}'
                pyproject_path.write_text("".join(lines))
                print(f"[bsk-sdk] Updated package version: {version} -> {pyproject_path}")
                return

    raise RuntimeError(f"Could not find [project].version in {pyproject_path}")


def update_extension_requirements(pyproject_path: Path, version: str) -> None:
    """Pin the example's build and runtime requirements to one BSK release."""
    contents = pyproject_path.read_text(encoding="utf-8")
    expected_counts = {"bsk-sdk": 1, "bsk": 2}

    for package, expected_count in expected_counts.items():
        requirement = re.compile(
            rf'(?P<quote>["\']){re.escape(package)}'
            r'(?:\s*(?:===|==|~=|!=|<=|>=|<|>)\s*[^"\']+)?(?P=quote)'
        )
        contents, count = requirement.subn(
            lambda match: (
                f'{match.group("quote")}{package}=={version}{match.group("quote")}'
            ),
            contents,
        )
        if count != expected_count:
            raise RuntimeError(
                f"Expected {expected_count} {package} requirement(s) in "
                f"{pyproject_path}; found {count}"
            )

    pyproject_path.write_text(contents, encoding="utf-8")
    print(
        f"[bsk-sdk] Updated example BSK and bsk-sdk requirements: "
        f"{version} -> {pyproject_path}"
    )


def stamp_bsk_version(
    bsk_root: Path,
    repo_root: Path,
    *,
    update_examples: bool = True,
) -> None:
    """Read the Basilisk version and update the selected SDK metadata."""
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
    update_pyproject_version(repo_root / "pyproject.toml", bsk_version)
    if update_examples:
        update_extension_requirements(
            repo_root / "examples" / "custom-atm-extension" / "pyproject.toml",
            bsk_version,
        )


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


def describe_basilisk_source(bsk_root: Path) -> str:
    """Return a readable path and Git revision for the selected checkout."""
    result = subprocess.run(
        ["git", "-C", str(bsk_root), "rev-parse", "--verify", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    revision = (
        result.stdout.strip() if result.returncode == 0 else "not a Git checkout"
    )
    return f"{bsk_root} @ {revision}"


def uses_default_basilisk_submodule(basilisk_root: str | None) -> bool:
    """Return whether synchronization selected the SDK's Basilisk submodule."""
    selected_root = basilisk_root or os.environ.get(BSK_BASILISK_ROOT_ENV)
    if not selected_root:
        return True
    return (
        Path(selected_root).expanduser().resolve()
        == DEFAULT_BASILISK_SUBMODULE_DIR.resolve()
    )


def should_update_default_submodule(basilisk_root: str | None) -> bool:
    """Return whether the default source is absent or a Git submodule.

    CI may place a standalone clone at ``external/basilisk`` to test another
    branch or tag. Such a clone has its own ``.git`` directory and must not be
    reset to the SDK's recorded submodule commit.
    """
    return uses_default_basilisk_submodule(basilisk_root) and not (
        DEFAULT_BASILISK_SUBMODULE_DIR / ".git"
    ).is_dir()


def main(arguments: Sequence[str] | None = None) -> int:
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
    submodule_group = ap.add_mutually_exclusive_group()
    submodule_group.add_argument(
        "--sync-submodules",
        action="store_true",
        help=(
            "Update external/basilisk before syncing. This is automatic when "
            "that submodule is the selected Basilisk source."
        ),
    )
    submodule_group.add_argument(
        "--no-sync-submodules",
        action="store_true",
        help=(
            "Do not update external/basilisk, even when it is the selected "
            "Basilisk source."
        ),
    )
    ap.add_argument(
        "--skip-example-updates",
        action="store_true",
        help=(
            "Synchronize only SDK build artifacts; do not update repository "
            "example requirements or Rust manifests."
        ),
    )
    args = ap.parse_args(arguments)

    tools_dir = (
        Path(args.sdk_tools_dir).resolve()
        if args.sdk_tools_dir
        else Path(__file__).resolve().parent
    )
    py = args.python
    basilisk_root = str(Path(args.basilisk_root).resolve()) if args.basilisk_root else None
    repo_root = tools_dir.parent

    update_default_submodule = should_update_default_submodule(basilisk_root)
    if args.sync_submodules or (
        update_default_submodule and not args.no_sync_submodules
    ):
        sync_basilisk_submodule(repo_root)

    # Stamp BSK version from the resolved Basilisk source tree.
    bsk_root = resolve_basilisk_root(basilisk_root)
    print(
        f"\n[bsk-sdk] Selected Basilisk source: {describe_basilisk_source(bsk_root)}",
        flush=True,
    )
    stamp_bsk_version(
        bsk_root,
        repo_root,
        update_examples=not args.skip_example_updates,
    )

    scripts = [
        "sync_headers.py",
        "sync_c_msg_interfaces.py",
        "sync_runtime.py",
        "sync_sources.py",
        "sync_swig.py",
        "sync_rust.py",
    ]

    for s in scripts:
        p = tools_dir / s
        if not p.exists():
            raise FileNotFoundError(f"Missing {p}")
        cmd = [py, str(p)]
        if s == "sync_rust.py" and args.skip_example_updates:
            cmd.append("--skip-example-updates")
        if basilisk_root:
            cmd.extend(["--basilisk-root", basilisk_root])
        run(cmd, cwd=tools_dir)

    print("\nAll sync steps completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
