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

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sync_all as sync_all_module  # noqa: E402
import sync_rust as sync_rust_module  # noqa: E402
from sync_all import (  # noqa: E402
    describe_basilisk_source,
    should_update_default_submodule,
    stamp_bsk_version,
    update_extension_requirements,
    update_pyproject_version,
    uses_default_basilisk_submodule,
)
from sync_rust import (  # noqa: E402
    BASILISK_GIT_URL,
    RUST_CMAKE_FILES,
    RUST_LICENSE_FILES,
    SUPPORT_MANIFEST_FILE,
    SUPPORT_VERSIONS_FILE,
    _dependency_specification,
    sync_example_versions,
    sync_rust_support,
)


def _write_rust_support_crates(basilisk_root: Path) -> None:
    """Create the four package manifests needed by local path dependencies."""
    for crate in ("bsk_build", "bsk_macros", "bsk_messages", "bsk_utilities"):
        manifest = (
            basilisk_root
            / "src"
            / "architecture"
            / "rust"
            / crate
            / "Cargo.toml"
        )
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            f'[package]\nname = "{crate.replace("_", "-")}"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )


def _write_example_manifests(sdk_root: Path) -> tuple[Path, Path]:
    """Create minimal copyable manifests for Rust synchronization tests."""
    example = sdk_root / "examples" / "custom-atm-extension"
    module = example / "rustAtmosphere"
    module.mkdir(parents=True)
    workspace = example / "Cargo.toml"
    workspace.write_text(
        "\n".join(
            [
                "[workspace.package]",
                'rust-version = "1.80"',
                "[workspace.dependencies]",
                'bsk-build = { version = "=0.0.1", git = "old", branch = "old" }',
                'bsk-messages = { version = "=0.0.1", git = "old", branch = "old" }',
                "",
            ]
        ),
        encoding="utf-8",
    )
    module_manifest = module / "Cargo.toml"
    module_manifest.write_text(
        "[build-dependencies]\n"
        'bsk-build = { version = "=0.0.1", git = "old", branch = "old", '
        'default-features = false, features = ["codegen"] }\n',
        encoding="utf-8",
    )
    return workspace, module_manifest


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


def test_update_extension_requirements_pins_build_and_runtime(tmp_path: Path) -> None:
    """The copyable example records its exact SDK and BSK compatibility."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "\n".join(
            [
                "[build-system]",
                'requires = ["bsk-sdk", "bsk", "swig==4.4.1"]',
                "",
                "[project]",
                'dependencies = ["bsk>=2.11", "numba"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    update_extension_requirements(pyproject, "2.12.0b0")

    contents = pyproject.read_text(encoding="utf-8")
    assert contents.count('"bsk==2.12.0b0"') == 2
    assert contents.count('"bsk-sdk==2.12.0b0"') == 1
    assert '"swig==4.4.1"' in contents
    assert '"numba"' in contents


def test_update_extension_requirements_rejects_missing_entries(tmp_path: Path) -> None:
    """Synchronization fails rather than silently omitting an exact requirement."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[build-system]\nrequires = ["bsk-sdk", "bsk"]\n', encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="Expected 2 bsk requirement"):
        update_extension_requirements(pyproject, "2.12.0")


def test_stamp_bsk_version_skips_absent_repository_examples(tmp_path: Path) -> None:
    """An sdist can synchronize SDK metadata without its excluded examples."""
    basilisk_root = tmp_path / "basilisk"
    version_file = basilisk_root / "docs" / "source" / "bskVersion.txt"
    version_file.parent.mkdir(parents=True)
    version_file.write_text("2.12.0b0\n", encoding="utf-8")

    sdk_root = tmp_path / "sdk"
    (sdk_root / "src" / "bsk_sdk").mkdir(parents=True)
    (sdk_root / "pyproject.toml").write_text(
        '[project]\nname = "bsk-sdk"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )

    stamp_bsk_version(basilisk_root, sdk_root, update_examples=False)

    assert (sdk_root / "src" / "bsk_sdk" / "_bsk_version.txt").read_text(
        encoding="utf-8"
    ) == "2.12.0b0\n"
    assert 'version = "2.12.0b0"' in (
        sdk_root / "pyproject.toml"
    ).read_text(encoding="utf-8")


@pytest.mark.parametrize("conflicting_flags", [False, True])
def test_refresh_example_rejects_invalid_setup_before_sync(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    conflicting_flags: bool,
) -> None:
    monkeypatch.setattr(sync_all_module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        sync_all_module, "should_update_default_submodule",
        lambda _root: pytest.fail("invalid setup must fail before synchronization"),
    )
    arguments = ["--refresh-example"]
    if conflicting_flags:
        arguments.append("--skip-example-updates")
    with pytest.raises(SystemExit) as error:
        sync_all_module.main(arguments)
    assert error.value.code == 2
    message = "not allowed with argument" if conflicting_flags else "requires Cargo on PATH"
    assert message in capsys.readouterr().err


@pytest.mark.parametrize("fetch_fails", [False, True])
@pytest.mark.parametrize("install_location", ["CARGO_INSTALL_ROOT", "CARGO_HOME", "default"])
def test_refresh_example_uses_synced_license_tool_and_stops_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fetch_fails: bool,
    install_location: str,
) -> None:
    sdk = tmp_path / "sdk with spaces"
    rust = sdk / "src" / "bsk_sdk" / "rust"
    rust.mkdir(parents=True)
    (rust / "support-versions.json").write_text(
        json.dumps({"BSK_CARGO_ABOUT_VERSION": "9.8.7"}), encoding="utf-8"
    )
    user_home = tmp_path / "user home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: user_home))
    monkeypatch.delenv("CARGO_INSTALL_ROOT", raising=False)
    monkeypatch.delenv("CARGO_HOME", raising=False)
    install_root = user_home / ".cargo"
    if install_location != "default":
        install_root = tmp_path / "installed tools"
        monkeypatch.setenv(install_location, str(install_root))
    if install_location == "CARGO_INSTALL_ROOT":
        monkeypatch.setenv("CARGO_HOME", str(tmp_path / "different cargo home"))

    # An older tool on PATH must not shadow the newly installed version.
    old_bin = tmp_path / "old tools"
    old_bin.mkdir()
    executable = "cargo-about.exe" if os.name == "nt" else "cargo-about"
    old_tool = old_bin / executable
    old_tool.write_text("old tool", encoding="utf-8")
    old_tool.chmod(0o755)
    monkeypatch.setenv("PATH", str(old_bin))
    original_env = os.environ.copy()
    commands: list[list[str]] = []

    def record(
        command: list[str], *, cwd: str, check: bool, env: dict[str, str] | None
    ) -> None:
        assert cwd == str(sdk)
        assert check is True
        commands.append(command)
        if command[1] == "install":
            assert env is None
            destination = Path(command[command.index("--root") + 1]) / "bin" / executable
            destination.parent.mkdir(parents=True)
            destination.write_text("pinned tool", encoding="utf-8")
            destination.chmod(0o755)
        if command[0] == "/selected python":
            assert env is not None
            assert Path(shutil.which("cargo-about", path=env["PATH"])) == install_root / "bin" / executable
            assert env == {**original_env, "PATH": str(install_root / "bin") + os.pathsep + str(old_bin)}
        if fetch_fails and command[1] == "fetch":
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(sync_all_module.subprocess, "run", record)
    if fetch_fails:
        with pytest.raises(subprocess.CalledProcessError):
            sync_all_module.refresh_example(sdk, "/selected python", "/selected cargo")
        assert len(commands) == 2
    else:
        sync_all_module.refresh_example(sdk, "/selected python", "/selected cargo")
        assert len(commands) == 4
        assert commands[2] == [
            "/selected cargo", "install", "cargo-about", "--version", "=9.8.7",
            "--locked", "--features", "cli", "--root", str(install_root),
        ]
        assert commands[3][:2] == [
            "/selected python", str(rust / "licenses" / "generate_rust_licenses.py")
        ]
        assert "--require-tool" in commands[3]
        assert str(sdk / "examples" / "custom-atm-extension" / "custom_atm" /
                   "RUST-THIRD-PARTY.txt") in commands[3]

    manifest = str(sdk / "examples" / "custom-atm-extension" / "Cargo.toml")
    assert commands[0] == ["/selected cargo", "generate-lockfile", "--manifest-path", manifest]
    assert commands[1] == ["/selected cargo", "fetch", "--manifest-path", manifest, "--locked"]
    assert os.environ == original_env


@pytest.mark.parametrize(
    ("example_flag", "expected_update_examples"),
    [(None, True), ("--skip-example-updates", False), ("--refresh-example", True)],
)
@pytest.mark.parametrize("local_rust_dependencies", [False, True])
def test_sync_all_selects_example_update_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    example_flag: str | None,
    expected_update_examples: bool,
    local_rust_dependencies: bool,
) -> None:
    """Manual sync maintains examples while artifact-only sync omits them."""
    basilisk_root = tmp_path / "basilisk"
    basilisk_root.mkdir()
    stamp_calls: list[bool] = []
    commands: list[list[str]] = []
    refresh_calls: list[tuple[Path, str, str]] = []

    def refresh(sdk: Path, python: str, cargo: str) -> None:
        assert Path(commands[-1][1]).name == "sync_rust.py"
        refresh_calls.append((sdk, python, cargo))

    def find_cargo(name: str) -> str:
        assert example_flag == "--refresh-example"
        assert name == "cargo"
        return "/toolchain with spaces/cargo"

    monkeypatch.setattr(sync_all_module.shutil, "which", find_cargo)
    monkeypatch.setattr(sync_all_module, "refresh_example", refresh)

    monkeypatch.setattr(
        sync_all_module,
        "resolve_basilisk_root",
        lambda _root: basilisk_root,
    )
    monkeypatch.setattr(
        sync_all_module,
        "stamp_bsk_version",
        lambda _bsk, _sdk, *, update_examples: stamp_calls.append(update_examples),
    )
    monkeypatch.setattr(
        sync_all_module,
        "run",
        lambda command, _cwd=None, **_kwargs: commands.append(command),
    )

    arguments = ["--basilisk-root", str(basilisk_root)]
    if example_flag:
        arguments.append(example_flag)
    if local_rust_dependencies:
        arguments.append("--local-rust-dependencies")
    result = sync_all_module.main(arguments)

    assert result == 0
    assert stamp_calls == [expected_update_examples]
    rust_command = next(
        command for command in commands if command[1].endswith("sync_rust.py")
    )
    assert ("--skip-example-updates" in rust_command) is (not expected_update_examples)
    assert refresh_calls == (
        [(Path(sync_all_module.__file__).resolve().parents[1], sys.executable,
          "/toolchain with spaces/cargo")]
        if example_flag == "--refresh-example" else []
    )
    assert ("--local-rust-dependencies" in rust_command) is local_rust_dependencies
    assert all(
        "--local-rust-dependencies" not in command
        for command in commands
        if command is not rust_command
    )
    assert not any(command[0] == "git" for command in commands)


@pytest.mark.parametrize("select_explicitly", [False, True])
def test_sync_all_updates_selected_default_submodule(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    select_explicitly: bool,
) -> None:
    """The default SDK submodule is initialized before its files are copied."""
    basilisk_root = tmp_path / "external" / "basilisk"
    basilisk_root.mkdir(parents=True)
    commands: list[list[str]] = []

    monkeypatch.delenv("BSK_BASILISK_ROOT", raising=False)
    monkeypatch.setattr(
        sync_all_module,
        "DEFAULT_BASILISK_SUBMODULE_DIR",
        basilisk_root,
    )
    monkeypatch.setattr(
        sync_all_module,
        "resolve_basilisk_root",
        lambda _root: basilisk_root,
    )
    monkeypatch.setattr(sync_all_module, "describe_basilisk_source", lambda _root: "test")
    monkeypatch.setattr(sync_all_module, "stamp_bsk_version", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sync_all_module,
        "run",
        lambda command, _cwd=None, **_kwargs: commands.append(command),
    )

    arguments = ["--basilisk-root", str(basilisk_root)] if select_explicitly else []
    assert sync_all_module.main(arguments) == 0

    assert commands[0] == [
        "git",
        "submodule",
        "update",
        "--init",
        "--recursive",
        "external/basilisk",
    ]


def test_sync_all_can_preserve_manually_moved_submodule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit opt-out preserves an intentionally unrecorded checkout."""
    basilisk_root = tmp_path / "external" / "basilisk"
    basilisk_root.mkdir(parents=True)
    commands: list[list[str]] = []

    monkeypatch.delenv("BSK_BASILISK_ROOT", raising=False)
    monkeypatch.setattr(
        sync_all_module,
        "DEFAULT_BASILISK_SUBMODULE_DIR",
        basilisk_root,
    )
    monkeypatch.setattr(
        sync_all_module,
        "resolve_basilisk_root",
        lambda _root: basilisk_root,
    )
    monkeypatch.setattr(sync_all_module, "describe_basilisk_source", lambda _root: "test")
    monkeypatch.setattr(sync_all_module, "stamp_bsk_version", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sync_all_module,
        "run",
        lambda command, _cwd=None, **_kwargs: commands.append(command),
    )

    assert sync_all_module.main(["--no-sync-submodules"]) == 0

    assert not any(command[0] == "git" for command in commands)


def test_describe_basilisk_source_reports_exact_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Synchronization identifies its input with an exact Git commit ID."""
    commit_id = "71cad7cf99dc9d9f5355ee89fc65cba36f264d69"
    monkeypatch.setattr(
        sync_all_module.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout=f"{commit_id}\n", stderr=""
        ),
    )

    assert describe_basilisk_source(tmp_path) == f"{tmp_path} @ {commit_id}"


def test_default_submodule_selection_honors_environment_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the SDK-owned checkout is eligible for automatic Git updates."""
    default_root = tmp_path / "external" / "basilisk"
    monkeypatch.setattr(
        sync_all_module,
        "DEFAULT_BASILISK_SUBMODULE_DIR",
        default_root,
    )
    monkeypatch.setenv("BSK_BASILISK_ROOT", str(tmp_path / "local-basilisk"))

    assert not uses_default_basilisk_submodule(None)


def test_standalone_clone_at_default_path_is_not_reset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CI clone occupying the submodule path retains its selected Git ref."""
    default_root = tmp_path / "external" / "basilisk"
    (default_root / ".git").mkdir(parents=True)
    monkeypatch.setattr(
        sync_all_module,
        "DEFAULT_BASILISK_SUBMODULE_DIR",
        default_root,
    )

    assert not should_update_default_submodule(str(default_root))


@pytest.mark.parametrize("local_rust_dependencies", [False, True])
def test_sync_rust_skip_mode_does_not_require_examples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, local_rust_dependencies: bool
) -> None:
    """Rust support copying succeeds when an sdist has no example workspace."""
    basilisk_root = tmp_path / "basilisk"
    version_file = basilisk_root / "docs" / "source" / "bskVersion.txt"
    version_file.parent.mkdir(parents=True)
    version_file.write_text("2.12.0b0\n", encoding="utf-8")
    sdk_rust_root = tmp_path / "sdk" / "src" / "bsk_sdk" / "rust"
    sdk_rust_root.mkdir(parents=True)
    (sdk_rust_root / SUPPORT_VERSIONS_FILE).write_text(
        json.dumps(
            {
                "BSK_RUST_MIN_VERSION": "1.89",
                "BSK_RUST_SUPPORT_CRATE_VERSION": "0.1.0",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sync_rust_module,
        "resolve_basilisk_root",
        lambda _root: basilisk_root,
    )
    monkeypatch.setattr(sync_rust_module, "SDK_RUST_ROOT", sdk_rust_root)
    monkeypatch.setattr(sync_rust_module, "sync_rust_support", lambda _root: 0)
    monkeypatch.setattr(
        sync_rust_module,
        "sync_example_versions",
        lambda *_args, **_kwargs: pytest.fail("example update should be skipped"),
    )

    arguments = ["--skip-example-updates"]
    if local_rust_dependencies:
        arguments.append("--local-rust-dependencies")
    sync_rust_module.main(arguments)


def test_sync_rust_support_replaces_generated_tree(tmp_path: Path) -> None:
    """Rust support synchronization copies the exact core-owned file set."""
    basilisk_root = tmp_path / "basilisk"
    cmake_root = basilisk_root / "src" / "cmake"
    cmake_root.mkdir(parents=True)
    for filename in RUST_CMAKE_FILES:
        contents = f"core {filename}\n"
        if filename == "bskRustSupportVersions.cmake":
            contents += "\n".join(
                [
                    'set(BSK_RUST_MIN_VERSION "1.89")',
                    'set(BSK_RUST_SUPPORT_CRATE_VERSION "0.1.0")',
                    'set(BSK_CORROSION_VERSION "0.6.1")',
                    'set(BSK_CORROSION_GIT_TAG "abc123")',
                    "",
                ]
            )
        (cmake_root / filename).write_text(contents)
    for source_relative, _ in RUST_LICENSE_FILES:
        source = basilisk_root / "src" / source_relative
        source.parent.mkdir(parents=True, exist_ok=True)
        contents = f"license support {source.name}\n"
        if source.name == "generate_rust_licenses.py":
            contents += 'CARGO_ABOUT_VERSION = "0.9.1"\n'
        source.write_text(contents)

    destination = tmp_path / "sdk-rust"
    destination.mkdir()
    (destination / "stale.txt").write_text("stale\n")

    copied = sync_rust_support(basilisk_root, destination)

    assert copied == len(RUST_CMAKE_FILES) + len(RUST_LICENSE_FILES)
    assert not (destination / "stale.txt").exists()
    for filename in RUST_CMAKE_FILES:
        assert (destination / "cmake" / filename).read_text().startswith(
            f"core {filename}\n"
        )
    for source_relative, destination_relative in RUST_LICENSE_FILES:
        source_name = Path(source_relative).name
        synchronized = (destination / destination_relative).read_text()
        assert synchronized.startswith(f"license support {source_name}\n")
    manifest = (destination / SUPPORT_MANIFEST_FILE).read_text()
    for filename in RUST_CMAKE_FILES:
        assert f"cmake/{filename}" in manifest
    for _, destination_relative in RUST_LICENSE_FILES:
        assert destination_relative in manifest
    versions = json.loads((destination / SUPPORT_VERSIONS_FILE).read_text())
    assert versions["BSK_RUST_MIN_VERSION"] == "1.89"
    assert versions["BSK_RUST_SUPPORT_CRATE_VERSION"] == "0.1.0"
    assert versions["BSK_CORROSION_GIT_TAG"] == "abc123"
    assert versions["BSK_CARGO_ABOUT_VERSION"] == "0.9.1"


@pytest.mark.parametrize(
    ("bsk_version", "local_dependencies"),
    [("2.12.0b0", False), ("2.12.0rc1", True), ("2.12.0", True)],
)
def test_sync_example_versions_updates_all_copyable_manifests(
    tmp_path: Path, bsk_version: str, local_dependencies: bool
) -> None:
    """Development and nightly RC/final sync select the exact local checkout."""
    workspace_path, module_path = _write_example_manifests(tmp_path)
    basilisk_root = tmp_path / "basilisk"
    _write_rust_support_crates(basilisk_root)

    sync_example_versions(
        tmp_path,
        {
            "BSK_RUST_MIN_VERSION": "1.89",
            "BSK_RUST_SUPPORT_CRATE_VERSION": "0.1.0",
        },
        bsk_version,
        basilisk_root,
        local_dependencies=local_dependencies,
    )

    workspace = workspace_path.read_text(encoding="utf-8")
    module_manifest = module_path.read_text(encoding="utf-8")
    assert 'rust-version = "1.89"' in workspace
    assert 'git = ' not in workspace
    assert 'path = ' in workspace
    assert 'tag = ' not in workspace
    assert workspace.count('version = "=0.1.0"') == 2
    assert 'version = "=0.1.0"' in module_manifest
    crate_root = basilisk_root / "src/architecture/rust"
    bsk_build_path = (crate_root / "bsk_build").resolve().as_posix()
    bsk_messages_path = (crate_root / "bsk_messages").resolve().as_posix()
    assert bsk_build_path in workspace
    assert bsk_messages_path in workspace
    assert bsk_build_path in module_manifest


def test_sync_example_versions_pins_release_tag(
    tmp_path: Path,
) -> None:
    """Final releases use the matching immutable BSK tag."""
    workspace_path, module_path = _write_example_manifests(tmp_path)
    basilisk_root = tmp_path / "basilisk"

    sync_example_versions(
        tmp_path,
        {
            "BSK_RUST_MIN_VERSION": "1.89",
            "BSK_RUST_SUPPORT_CRATE_VERSION": "0.1.0",
        },
        "2.12.1",
        basilisk_root,
    )

    workspace = workspace_path.read_text(encoding="utf-8")
    module_manifest = module_path.read_text(encoding="utf-8")
    assert workspace.count('tag = "v2.12.1"') == 2
    assert 'branch = ' not in workspace
    assert f'git = "{BASILISK_GIT_URL}"' in workspace
    assert 'tag = "v2.12.1"' in module_manifest


@pytest.mark.parametrize(
    ("bsk_version", "local_dependencies"),
    [("2.12.0b0", False), ("2.12.0rc1", True), ("2.12.0", True)],
)
def test_sync_example_versions_uses_portable_submodule_paths(
    tmp_path: Path, bsk_version: str, local_dependencies: bool
) -> None:
    """The default SDK submodule does not introduce machine-specific paths."""
    workspace_path, module_path = _write_example_manifests(tmp_path)
    basilisk_root = tmp_path / "external" / "basilisk"
    _write_rust_support_crates(basilisk_root)

    sync_example_versions(
        tmp_path,
        {
            "BSK_RUST_MIN_VERSION": "1.89",
            "BSK_RUST_SUPPORT_CRATE_VERSION": "0.1.0",
        },
        bsk_version,
        basilisk_root,
        local_dependencies=local_dependencies,
    )

    workspace = workspace_path.read_text(encoding="utf-8")
    module_manifest = module_path.read_text(encoding="utf-8")
    assert (
        'path = "../../external/basilisk/src/architecture/rust/bsk_build"'
        in workspace
    )
    assert (
        'path = "../../external/basilisk/src/architecture/rust/bsk_messages"'
        in workspace
    )
    assert (
        'path = "../../../external/basilisk/src/architecture/rust/bsk_build"'
        in module_manifest
    )
    assert str(tmp_path.resolve()) not in workspace
    assert str(tmp_path.resolve()) not in module_manifest


def test_sync_example_versions_pins_release_candidate_tag(tmp_path: Path) -> None:
    """Release candidates follow the existing SDK tag publication workflow."""
    workspace_path, _ = _write_example_manifests(tmp_path)

    sync_example_versions(
        tmp_path,
        {
            "BSK_RUST_MIN_VERSION": "1.89",
            "BSK_RUST_SUPPORT_CRATE_VERSION": "0.1.0",
        },
        "2.12.0rc1",
        tmp_path / "basilisk",
    )

    workspace = workspace_path.read_text(encoding="utf-8")
    assert workspace.count('tag = "v2.12.0rc1"') == 2


def test_tagged_git_dependencies_resolve_nested_support_crates(
    tmp_path: Path,
) -> None:
    """Cargo resolves the release specification from BSK's nested workspace."""
    cargo = shutil.which("cargo")
    git = shutil.which("git")
    if cargo is None or git is None:
        pytest.skip("Cargo and Git are required for the tagged dependency test")

    basilisk = tmp_path / "basilisk"
    rust_root = basilisk / "src" / "architecture" / "rust"
    bsk_build = rust_root / "bsk_build"
    bsk_messages = rust_root / "bsk_messages"
    bsk_build.mkdir(parents=True)
    bsk_messages.mkdir(parents=True)
    (basilisk / "src" / "Cargo.toml").write_text(
        "[workspace]\n"
        'members = ["architecture/rust/bsk_build", '
        '"architecture/rust/bsk_messages"]\n'
        'resolver = "2"\n',
        encoding="utf-8",
    )
    (bsk_build / "Cargo.toml").write_text(
        "[package]\n"
        'name = "bsk-build"\n'
        'version = "0.1.0"\n'
        'edition = "2021"\n'
        "[lib]\n"
        'path = "lib.rs"\n',
        encoding="utf-8",
    )
    (bsk_build / "lib.rs").write_text(
        "pub fn build_marker() -> u32 { 1 }\n", encoding="utf-8"
    )
    (bsk_messages / "Cargo.toml").write_text(
        "[package]\n"
        'name = "bsk-messages"\n'
        'version = "0.1.0"\n'
        'edition = "2021"\n'
        "[dependencies]\n"
        'bsk-build = { version = "=0.1.0", path = "../bsk_build" }\n'
        "[lib]\n"
        'path = "lib.rs"\n',
        encoding="utf-8",
    )
    (bsk_messages / "lib.rs").write_text(
        "pub fn message_marker() -> u32 { bsk_build::build_marker() }\n",
        encoding="utf-8",
    )

    for command in (
        [git, "init"],
        [git, "config", "user.email", "bsk-sdk-test@example.invalid"],
        [git, "config", "user.name", "bsk-sdk test"],
        [git, "add", "."],
        [git, "commit", "-m", "test support crates"],
        [git, "tag", "v2.12.1"],
    ):
        subprocess.run(command, cwd=basilisk, check=True, capture_output=True)

    extension = tmp_path / "extension"
    (extension / "src").mkdir(parents=True)
    git_url = basilisk.resolve().as_uri()
    bsk_build_spec = _dependency_specification(
        "0.1.0", tag="v2.12.1", git_url=git_url
    )
    bsk_messages_spec = _dependency_specification(
        "0.1.0", tag="v2.12.1", git_url=git_url
    )
    (extension / "Cargo.toml").write_text(
        "[package]\n"
        'name = "tagged-extension-check"\n'
        'version = "0.1.0"\n'
        'edition = "2021"\n'
        "[dependencies]\n"
        f"bsk-build = {bsk_build_spec}\n"
        f"bsk-messages = {bsk_messages_spec}\n",
        encoding="utf-8",
    )
    (extension / "src" / "lib.rs").write_text(
        "pub fn support_marker() -> u32 {\n"
        "    bsk_build::build_marker() + bsk_messages::message_marker()\n"
        "}\n",
        encoding="utf-8",
    )

    cargo_environment = os.environ.copy()
    cargo_environment["CARGO_HOME"] = str(tmp_path / "cargo-home")

    lock_result = subprocess.run(
        [cargo, "generate-lockfile"],
        cwd=extension,
        check=False,
        capture_output=True,
        text=True,
        env=cargo_environment,
    )
    assert lock_result.returncode == 0, lock_result.stderr
    subprocess.run(
        [cargo, "check", "--locked", "--offline"],
        cwd=extension,
        check=True,
        capture_output=True,
        env=cargo_environment,
    )
    metadata = subprocess.run(
        [cargo, "metadata", "--locked", "--offline", "--format-version=1"],
        cwd=extension,
        check=True,
        capture_output=True,
        text=True,
        env=cargo_environment,
    )
    support_packages = {
        package["name"]: package["source"]
        for package in json.loads(metadata.stdout)["packages"]
        if package["name"] in {"bsk-build", "bsk-messages"}
    }
    assert set(support_packages) == {"bsk-build", "bsk-messages"}
    assert all(source.startswith("git+file://") for source in support_packages.values())
