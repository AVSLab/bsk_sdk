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
Smoke tests for the installed bsk-sdk wheel.

Verifies that the package is importable, all advertised paths exist on disk,
and the CMake config directory contains the expected files.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import bsk_sdk


def test_package_root_exists() -> None:
    root = bsk_sdk.package_root()
    assert Path(root).is_dir(), f"package_root() does not exist: {root}"


def test_include_dirs_exist() -> None:
    for d in bsk_sdk.include_dirs():
        assert Path(d).is_dir(), f"include dir missing: {d}"


def test_swig_dir_exists() -> None:
    assert Path(bsk_sdk.swig_dir()).is_dir()


def test_messaging_base_swig_interface_present() -> None:
    """The installed SDK includes the shared messaging base interface."""
    messaging_base = (
        Path(bsk_sdk.swig_dir())
        / "architecture"
        / "messaging"
        / "messagingBase.i"
    )
    assert messaging_base.is_file()


def test_tools_dir_exists() -> None:
    tools = Path(bsk_sdk.tools_dir())
    assert tools.is_dir()
    assert (tools / "_versioning.py").is_file()
    assert (tools / "sync_rust.py").is_file()


def test_cmake_config_dir_exists() -> None:
    assert Path(bsk_sdk.cmake_config_dir()).is_dir()


def test_cmake_config_files_present() -> None:
    config_dir = Path(bsk_sdk.cmake_config_dir())
    assert (config_dir / "bsk-sdkConfig.cmake").exists()
    assert (config_dir / "bsk-sdkConfigVersion.cmake").exists()
    assert (config_dir / "bsk_add_swig_module.cmake").exists()
    assert (config_dir / "bsk_add_python_module.cmake").exists()
    assert (config_dir / "bsk_generate_messages.cmake").exists()
    assert (config_dir / "bsk_add_rust_module.cmake").exists()
    assert (config_dir / "bsk_extension_compatibility.cmake").exists()
    assert (config_dir / "bsk_extension_compatibility.py.in").exists()


def test_sdk_source_dirs_exist() -> None:
    root = Path(bsk_sdk.package_root())
    for d in ("arch_min", "arch_utilities", "runtime_min"):
        assert (root / d).is_dir(), f"SDK source dir missing: {d}"
        assert any((root / d).iterdir()), f"SDK source dir is empty: {d}"


def test_builtin_c_msg_interfaces_present() -> None:
    """Built-in C message wrappers ship pre-generated for C extension modules."""
    cmsg = Path(bsk_sdk.c_msg_interface_dir())
    assert cmsg.is_dir(), f"c_msg_interface_dir() does not exist: {cmsg}"
    for name in ("SpicePlanetStateMsg_C.h", "SpicePlanetStateMsg_C.cpp"):
        assert (cmsg / name).exists(), f"Missing built-in C message interface: {name}"


def test_rust_build_support_present() -> None:
    """The installed SDK carries synchronized Rust/CMake integration files."""
    rust = Path(bsk_sdk.rust_dir())
    manifest = rust / "support-manifest.txt"
    assert manifest.is_file()
    entries = [
        line.strip()
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    for relative in entries:
        assert (rust / relative).is_file(), f"Missing Rust support file: {relative}"

    assert bsk_sdk.rust_minimum_version()
    assert bsk_sdk.rust_support_crate_version()
    assert bsk_sdk.rust_license_tool_version()
    assert Path(bsk_sdk.rust_license_generator()).is_file()
    assert Path(bsk_sdk.rust_license_config()).is_file()
    libclang = Path(bsk_sdk.rust_libclang_dir())
    assert libclang.is_dir()
    assert any(path.name.startswith("libclang") for path in libclang.iterdir())


def test_relocated_rust_license_generator_requires_project_paths() -> None:
    """The installed generator rejects ambiguous source-tree defaults."""
    result = subprocess.run(
        [sys.executable, bsk_sdk.rust_license_generator()],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "--manifest-path" in result.stderr
    assert "--output" in result.stderr


def test_c_message_templates_present() -> None:
    """Language-neutral C-message templates are packaged outside Rust support."""
    templates = Path(bsk_sdk.package_root()) / "message_templates"
    assert (templates / "msg_C.h.in").is_file()
    assert (templates / "msg_C.cpp.in").is_file()


def test_rust_crate_sources_are_not_packaged_as_headers() -> None:
    """Versioned Rust crates are not duplicated under the SDK include tree."""
    include_root = Path(bsk_sdk.include_dir()) / "Basilisk" / "architecture"
    assert not (include_root / "rust").exists()


def test_msg_autosource_generators_present() -> None:
    autosrc = Path(bsk_sdk.msg_autosource_dir())
    assert autosrc.is_dir(), f"msg_autosource_dir() does not exist: {autosrc}"
    for name in (
        "generatePayloadEqualityHeader.py",
        "generatePayloadMetaJson.py",
        "generateSWIGModules.py",
        "msgInterfacePy.i.in",
        "cMsgCInterfacePy.i.in",
    ):
        assert (autosrc / name).exists(), f"Missing msgAutoSource file: {name}"


def test_message_source_keep_alive_support_present() -> None:
    """The installed SDK carries the Basilisk 2.12 message lifetime hooks."""
    package_root = Path(bsk_sdk.package_root())
    autosrc = Path(bsk_sdk.msg_autosource_dir())

    c_msg_template = (autosrc / "cMsgCInterfacePy.i.in").read_text()
    assert "_msgKeepAlive.retainSource(self, source)" in c_msg_template
    assert "_msgKeepAlive.retainRecorderSource(recorder, self)" in c_msg_template

    msg_template = (autosrc / "msgInterfacePy.i.in").read_text()
    assert (
        "_msgKeepAlive.retainRecorderConstructorSource(self, args[0], {type})"
        in msg_template
    )

    messaging_dir = (
        package_root / "include" / "Basilisk" / "architecture" / "messaging"
    )
    messaging_header = (messaging_dir / "messaging.h").read_text()
    assert "void setSource(void* handle" in messaging_header

    messaging_impl = (messaging_dir / "newMessaging.ih").read_text()
    assert "self._install_keepalive(source)" in messaging_impl
    assert "return self._recorder_with_keepalive(self, timeDiff)" in messaging_impl

    c_wrapper = (
        Path(bsk_sdk.swig_dir())
        / "architecture"
        / "_GeneralModuleFiles"
        / "swig_c_wrap.i"
    ).read_text()
    assert "_msgKeepAlive.registerModule(self)" in c_wrapper
    assert "_msgKeepAlive.transferModuleOwner(args[0], self)" in c_wrapper
