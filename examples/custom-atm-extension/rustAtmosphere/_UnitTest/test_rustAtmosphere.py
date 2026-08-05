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

"""Integration tests for the Rust module packaged by the SDK example wheel."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import bsk_sdk
import pytest

pytest.importorskip("Basilisk", reason="Basilisk not installed")
custom_atm = pytest.importorskip(
    "custom_atm", reason="custom_atm extension not installed"
)

from Basilisk.architecture import messaging as bsk_messaging  # noqa: E402
from Basilisk.architecture.bskLogging import BasiliskError  # noqa: E402
from Basilisk.utilities import SimulationBaseClass, macros  # noqa: E402
from custom_atm import messaging as extension_messaging  # noqa: E402
from custom_atm import rustAtmosphere  # noqa: E402


def _run_module(connect_custom_status: bool = True):
    """Execute three Rust updates and return the module and output recorders."""
    simulation = SimulationBaseClass.SimBaseClass()
    process = simulation.CreateNewProcess("rustProcess")
    task_period = macros.sec2nano(0.5)  # [ns]
    process.addTask(simulation.CreateNewTask("rustTask", task_period))

    module = rustAtmosphere.rustAtmosphere()
    module.ModelTag = "extensionRustAtmosphere"
    module.densityScale = 2.5  # [-]

    atmosphere_payload = bsk_messaging.AtmoPropsMsgPayload()
    atmosphere_payload.neutralDensity = 2.0e-12  # [kg/m^3]
    atmosphere_payload.localTemp = 275.0  # [K]
    atmosphere_source = bsk_messaging.AtmoPropsMsg().write(atmosphere_payload)
    module.atmoInMsg.subscribeTo(atmosphere_source)

    status_source = None
    if connect_custom_status:
        status_payload = extension_messaging.CustomAtmStatusMsgPayload()
        status_payload.density = 4.0e-12  # [kg/m^3]
        status_payload.scaleHeight = 8_500.0  # [m]
        status_payload.modelValid = 1
        status_source = extension_messaging.CustomAtmStatusMsg().write(status_payload)
        module.statusInMsg.subscribeTo(status_source)

    atmosphere_recorder = module.atmoOutMsg.recorder()
    status_recorder = module.statusOutMsg.recorder()
    simulation.AddModelToTask("rustTask", module)
    simulation.AddModelToTask("rustTask", atmosphere_recorder)
    simulation.AddModelToTask("rustTask", status_recorder)
    simulation.InitializeSimulation()
    simulation.ConfigureStopTime(2 * task_period)
    simulation.ExecuteSimulation()

    return module, atmosphere_recorder, status_recorder, task_period


def test_rust_extension_uses_core_and_custom_messages() -> None:
    """Rust reads and publishes built-in and extension-owned C messages."""
    module, atmosphere, status, task_period = _run_module()

    assert atmosphere.neutralDensity == pytest.approx([1.0e-11] * 3)
    assert atmosphere.localTemp == pytest.approx([275.0] * 3)
    assert status.density == pytest.approx([1.0e-11] * 3)
    assert status.scaleHeight == pytest.approx([8_500.0] * 3)
    assert list(status.modelValid) == [1] * 3
    assert list(atmosphere.times()) == [0, task_period, 2 * task_period]
    assert list(status.times()) == list(atmosphere.times())

    for output in (module.atmoOutMsg, module.statusOutMsg):
        assert output.header.isWritten
        assert output.header.moduleID == module.moduleID
        assert output.header.timeWritten == 2 * task_period


def test_rust_extension_optional_custom_input() -> None:
    """An unlinked custom input uses the built-in atmosphere as fallback."""
    _, atmosphere, status, _ = _run_module(connect_custom_status=False)

    assert atmosphere.neutralDensity == pytest.approx([5.0e-12] * 3)
    assert status.density == pytest.approx([5.0e-12] * 3)
    assert status.scaleHeight == pytest.approx([0.0] * 3)
    assert list(status.modelValid) == [0] * 3


def test_rust_extension_validates_configuration() -> None:
    """The generated Rust setter rejects an invalid density scale immediately."""
    module = rustAtmosphere.rustAtmosphere()
    with pytest.raises(
        BasiliskError,
        match="rustAtmosphere.densityScale must be finite and non-negative",
    ):
        module.densityScale = -1.0  # [-]

    assert module.densityScale == 1.0  # [-]


def test_example_uses_sdk_rust_support_versions() -> None:
    """Keep the copyable Cargo workspace aligned with synchronized SDK metadata."""
    manifest = Path(__file__).resolve().parents[2] / "Cargo.toml"
    cargo = shutil.which("cargo")
    assert cargo is not None, "Cargo must be available to test the Rust example"
    metadata_result = subprocess.run(
        [
            cargo,
            "metadata",
            "--no-deps",
            "--offline",
            "--format-version=1",
            "--locked",
            "--manifest-path",
            str(manifest),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    metadata = json.loads(metadata_result.stdout)
    rust_package = next(
        package
        for package in metadata["packages"]
        if package["name"] == "rustAtmosphere"
    )
    expected_support_version = f"={bsk_sdk.rust_support_crate_version()}"
    support_dependencies = [
        dependency
        for dependency in rust_package["dependencies"]
        if dependency["name"] in {"bsk-build", "bsk-messages"}
    ]

    assert rust_package["rust_version"] == bsk_sdk.rust_minimum_version()
    actual_dependencies = [
        (dependency["name"], dependency["kind"], dependency["req"])
        for dependency in support_dependencies
    ]
    actual_dependencies.sort(
        key=lambda dependency: (dependency[0], dependency[1] or "")
    )
    assert actual_dependencies == [
        ("bsk-build", None, expected_support_version),
        ("bsk-build", "build", expected_support_version),
        ("bsk-messages", None, expected_support_version),
    ]

    pyproject = manifest.parent / "pyproject.toml"
    package_metadata = pyproject.read_text(encoding="utf-8")
    expected_version = bsk_sdk.bsk_version()
    assert package_metadata.count(f'"bsk=={expected_version}"') == 2
    assert package_metadata.count(f'"bsk-sdk=={expected_version}"') == 1


def test_rust_dependency_license_report_is_packaged() -> None:
    """The installed extension wheel includes its Rust dependency notices."""
    report = Path(custom_atm.__file__).resolve().with_name("RUST-THIRD-PARTY.txt")

    assert report.is_file()
    contents = report.read_text(encoding="utf-8")
    assert "custom-atm-extension Rust Third-Party Licenses" in contents
    assert "Do not edit it by hand." in contents
