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

"""Incremental-build tests for extension-owned Rust message bindings."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import bsk_sdk
import pytest


def _bsk_messages_package(cargo: str) -> Path:
    """Resolve the exact ``bsk-messages`` package selected by Cargo."""
    workspace_manifest = Path(__file__).resolve().parents[2] / "Cargo.toml"
    result = subprocess.run(
        [
            cargo,
            "metadata",
            "--locked",
            "--offline",
            "--format-version=1",
            "--manifest-path",
            str(workspace_manifest),
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    packages = [
        package
        for package in json.loads(result.stdout)["packages"]
        if package["name"] == "bsk-messages"
    ]
    assert len(packages) == 1, "Cargo metadata must resolve exactly one bsk-messages"
    return Path(packages[0]["manifest_path"]).resolve().parent


def _payload_header(include_updated_field: bool) -> str:
    """Render a payload whose second revision changes only the included file."""
    updated_field = "    double updatedValue;\n" if include_updated_field else ""
    return (
        "#ifndef IncrementalMsgPayload_h\n"
        "#define IncrementalMsgPayload_h\n"
        "typedef struct {\n"
        "    double initialValue;\n"
        f"{updated_field}"
        "} IncrementalMsgPayload;\n"
        "#endif\n"
    )


def _c_interface_header(payload_header: Path) -> str:
    """Render the stable generated C interface that includes the payload."""
    include_path = payload_header.as_posix()
    return f"""#ifndef IncrementalMsg_C_H
#define IncrementalMsg_C_H
#include <stdint.h>
#include "{include_path}"
#include "architecture/messaging/msgHeader.h"
typedef struct {{
    MsgHeader header;
    IncrementalMsgPayload payload;
    IncrementalMsgPayload *payloadPointer;
    MsgHeader *headerPointer;
}} IncrementalMsg_C;
int IncrementalMsg_C_isLinked(IncrementalMsg_C *data);
IncrementalMsgPayload IncrementalMsg_C_read(IncrementalMsg_C *source);
void IncrementalMsg_C_init(IncrementalMsg_C *owner);
void IncrementalMsg_C_write(IncrementalMsgPayload *data,
                            IncrementalMsg_C *destination,
                            int64_t moduleID,
                            uint64_t callTime);
#endif
"""


def _consumer_source(field_name: str) -> str:
    """Render a consumer that proves the requested generated field exists."""
    return (
        "use bsk_messages::IncrementalMsg;\n\n"
        "fn main() {\n"
        "    let payload = IncrementalMsg::default();\n"
        f"    let _ = payload.{field_name};\n"
        "}\n"
    )


def test_payload_edit_regenerates_rust_bindings_without_cleaning(
    tmp_path: Path,
) -> None:
    """An included payload edit invalidates ``bsk-messages`` incrementally."""
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("Cargo is not installed")

    bsk_messages = _bsk_messages_package(cargo)

    payload_dir = tmp_path / "payloads"
    c_message_dir = tmp_path / "cMsgCInterface"
    consumer_dir = tmp_path / "consumer"
    source_dir = consumer_dir / "src"
    payload_dir.mkdir()
    c_message_dir.mkdir()
    source_dir.mkdir(parents=True)

    payload_header = payload_dir / "IncrementalMsgPayload.h"
    c_interface = c_message_dir / "IncrementalMsg_C.h"
    manifest = consumer_dir / "Cargo.toml"
    source = source_dir / "main.rs"

    payload_header.write_text(_payload_header(False), encoding="utf-8")
    c_interface.write_text(
        _c_interface_header(payload_header),
        encoding="utf-8",
    )
    manifest.write_text(
        "[package]\n"
        'name = "bsk-message-incremental-check"\n'
        'version = "0.1.0"\n'
        'edition = "2021"\n\n'
        "[dependencies]\n"
        f'bsk-messages = {{ path = "{bsk_messages.as_posix()}" }}\n',
        encoding="utf-8",
    )
    source.write_text(_consumer_source("initialValue"), encoding="utf-8")

    environment = os.environ.copy()
    environment.update(
        {
            "BSK_CMSG_DIRS": str(c_message_dir),
            "BSK_SRC_ROOT": str(Path(bsk_sdk.include_dir()) / "Basilisk"),
            "CARGO_TARGET_DIR": str(tmp_path / "target"),
        }
    )
    if sys.platform != "darwin":
        environment["LIBCLANG_PATH"] = bsk_sdk.rust_libclang_dir()
    # The example wheel build has already populated Cargo's dependency cache.
    # Staying offline makes this regression test deterministic and prevents an
    # incremental header check from depending on registry availability.
    command = [cargo, "check", "--offline", "--manifest-path", str(manifest)]
    subprocess.run(command, check=True, env=environment)

    previous_mtime = payload_header.stat().st_mtime
    payload_header.write_text(_payload_header(True), encoding="utf-8")
    os.utime(payload_header, (previous_mtime + 2.0, previous_mtime + 2.0))
    source.write_text(_consumer_source("updatedValue"), encoding="utf-8")

    # Reuse the same Cargo target directory. This succeeds only if the payload
    # include invalidates bsk-messages and regenerates its Rust bindings.
    subprocess.run(command, check=True, env=environment)
