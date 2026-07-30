# ISC License
#
# Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""Tests for automatic synchronization in the PEP 517 build backend."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _load_build_backend(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load the source backend without requiring its build-time dependency."""
    scikit_build_core = ModuleType("scikit_build_core")
    scikit_build_core.build = SimpleNamespace()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "scikit_build_core", scikit_build_core)

    backend_path = Path(__file__).resolve().parents[1] / "build_backend.py"
    specification = importlib.util.spec_from_file_location(
        "bsk_sdk_test_build_backend", backend_path
    )
    assert specification is not None and specification.loader is not None
    backend = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(backend)
    return backend


def _automatic_sync_command(
    monkeypatch: pytest.MonkeyPatch,
    *,
    basilisk_root: str | None = None,
    sync_submodules: str | None = None,
) -> list[str]:
    """Return the command issued by one automatic synchronization request."""
    backend = _load_build_backend(monkeypatch)
    monkeypatch.delenv("BSK_BASILISK_ROOT", raising=False)
    monkeypatch.delenv("BSK_SDK_SYNC_SUBMODULES", raising=False)
    if basilisk_root is not None:
        monkeypatch.setenv("BSK_BASILISK_ROOT", basilisk_root)
    if sync_submodules is not None:
        monkeypatch.setenv("BSK_SDK_SYNC_SUBMODULES", sync_submodules)

    calls: list[list[str]] = []

    def record_run(command, **_kwargs) -> None:
        """Record the subprocess command without executing synchronization."""
        calls.append(command)

    monkeypatch.setattr(backend.subprocess, "run", record_run)
    backend._run_sync()

    assert len(calls) == 1
    return calls[0]


def test_automatic_sync_updates_default_submodule(monkeypatch) -> None:
    """Automatic sync updates the SDK submodule when no source is selected."""
    command = _automatic_sync_command(monkeypatch)

    assert "--sync-submodules" in command
    assert "--skip-example-updates" in command
    assert "--basilisk-root" not in command


def test_automatic_sync_treats_empty_checkout_as_unset(monkeypatch) -> None:
    """An empty checkout override retains the default submodule behavior."""
    command = _automatic_sync_command(monkeypatch, basilisk_root="")

    assert "--sync-submodules" in command
    assert "--skip-example-updates" in command
    assert "--basilisk-root" not in command


def test_automatic_sync_uses_explicit_checkout_without_submodule(monkeypatch) -> None:
    """A selected local checkout does not require or update the SDK submodule."""
    local_basilisk = "/test/local-basilisk"
    command = _automatic_sync_command(monkeypatch, basilisk_root=local_basilisk)

    assert "--sync-submodules" not in command
    assert "--skip-example-updates" in command
    assert command[-2:] == ["--basilisk-root", local_basilisk]


def test_automatic_sync_honors_explicit_submodule_request(monkeypatch) -> None:
    """A caller may deliberately update the submodule and use another checkout."""
    local_basilisk = "/test/local-basilisk"
    command = _automatic_sync_command(
        monkeypatch,
        basilisk_root=local_basilisk,
        sync_submodules="1",
    )

    assert "--sync-submodules" in command
    assert command[-2:] == ["--basilisk-root", local_basilisk]
