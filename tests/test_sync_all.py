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

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from sync_all import update_pyproject_version  # noqa: E402


def test_update_pyproject_version_updates_project_table_only(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "\n".join(
            [
                "[project]",
                'name = "bsk-sdk"',
                'version = "2.11.0"',
                "",
                "[tool.scikit-build.cmake]",
                'version = ">=3.26"',
                "",
            ]
        )
    )

    update_pyproject_version(pyproject, "2.12.0b0")

    assert pyproject.read_text() == "\n".join(
        [
            "[project]",
            'name = "bsk-sdk"',
            'version = "2.12.0b0"',
            "",
            "[tool.scikit-build.cmake]",
            'version = ">=3.26"',
            "",
        ]
    )


def test_update_pyproject_version_requires_project_version(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "\n".join(
            [
                "[project]",
                'name = "bsk-sdk"',
                "",
                "[tool.scikit-build.cmake]",
                'version = ">=3.26"',
                "",
            ]
        )
    )

    with pytest.raises(RuntimeError, match=r"\[project\]\.version"):
        update_pyproject_version(pyproject, "2.12.0b0")
