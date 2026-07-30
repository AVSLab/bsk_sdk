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

"""Tests for BSK-SDK release-version policy."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from _versioning import is_publishable_bsk_version, main  # noqa: E402


@pytest.mark.parametrize("version", ["2.12.0", "2.12.1", "2.12.0rc1", "10.0.0rc12"])
def test_final_and_release_candidate_versions_are_publishable(version: str) -> None:
    """Final and release-candidate SDK versions may enter publication."""
    assert is_publishable_bsk_version(version)
    assert main([version]) == 0


@pytest.mark.parametrize(
    "version",
    [
        "2.12.0a0",
        "2.12.0b0",
        "2.12.0alpha1",
        "2.12.0beta1",
        "2.12.0.dev1",
        "2.12",
        "v2.12.0",
    ],
)
def test_development_versions_are_not_publishable(version: str) -> None:
    """All alpha, beta, development, and malformed versions are rejected."""
    assert not is_publishable_bsk_version(version)
    with pytest.raises(SystemExit) as error:
        main([version])
    assert error.value.code == 2
