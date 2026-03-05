#!/usr/bin/env python3

from __future__ import annotations

import os
from pathlib import Path

BSK_BASILISK_ROOT_ENV = "BSK_BASILISK_ROOT"
SDK_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASILISK_SUBMODULE_DIR = SDK_REPO_ROOT / "external" / "basilisk"


def resolve_basilisk_root(basilisk_root_arg: str | None) -> Path:
    if basilisk_root_arg:
        return Path(basilisk_root_arg).expanduser().resolve()

    env_root = os.environ.get(BSK_BASILISK_ROOT_ENV)
    if env_root:
        return Path(env_root).expanduser().resolve()

    if DEFAULT_BASILISK_SUBMODULE_DIR.exists():
        return DEFAULT_BASILISK_SUBMODULE_DIR.resolve()

    sibling = SDK_REPO_ROOT.parent / "basilisk"
    if sibling.exists():
        return sibling.resolve()

    raise RuntimeError(
        "Could not locate Basilisk repository root. "
        f"Set --basilisk-root or {BSK_BASILISK_ROOT_ENV}, "
        "or initialize external/basilisk submodule."
    )


def resolve_basilisk_src_root(basilisk_root_arg: str | None) -> Path:
    return resolve_basilisk_root(basilisk_root_arg) / "src"
