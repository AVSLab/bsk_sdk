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

"""Integration test for the extension-owned Numba Basilisk module."""

from __future__ import annotations

import importlib.util
from importlib import metadata
from pathlib import Path

import pytest
from packaging.requirements import Requirement

pytest.importorskip("Basilisk", reason="Basilisk not installed")
pytest.importorskip("numba", reason="numba not installed")
custom_atm = pytest.importorskip(
    "custom_atm", reason="custom_atm extension not installed"
)

from Basilisk.architecture import messaging as bsk_messaging  # noqa: E402
from Basilisk.utilities import SimulationBaseClass, macros  # noqa: E402
from custom_atm import numbaAtmosphere  # noqa: E402


def _load_scenario():
    """Load the repository example without adding its directory to ``sys.path``."""
    scenario_path = (
        Path(__file__).resolve().parents[3] / "scenarioNumbaAtmosphereExtension.py"
    )
    spec = importlib.util.spec_from_file_location(
        "scenarioNumbaAtmosphereExtension", scenario_path
    )
    assert spec is not None and spec.loader is not None
    scenario = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenario)
    return scenario


def test_numba_module_is_installed() -> None:
    """The extension wheel exposes the CMake-copied Python module."""
    assert hasattr(custom_atm, "numbaAtmosphere")
    assert custom_atm.numbaAtmosphere.__file__.endswith("numbaAtmosphere.py")


def test_extension_wheel_declares_numba_runtime_dependencies() -> None:
    """A clean wheel install pulls in both Basilisk and Numba."""
    requirements = metadata.requires("bsk-extension-exponential-atmosphere") or []
    names = {Requirement(requirement).name for requirement in requirements}

    assert {"bsk", "numba"} <= names


def test_custom_payload_is_registered_for_numba() -> None:
    """Generated extension payload dtypes are visible to NumbaModel."""
    assert (
        bsk_messaging.CustomAtmStatusMsgPayload
        is custom_atm.messaging.CustomAtmStatusMsgPayload
    )


def test_custom_payload_registration_rejects_name_collisions() -> None:
    """A second extension cannot silently replace a registered payload dtype."""

    class ConflictingPayload:
        pass

    ConflictingPayload.__name__ = "CustomAtmStatusMsgPayload"
    with pytest.raises(ImportError, match="already exposes a different payload class"):
        custom_atm.messaging._register_numba_payload(ConflictingPayload)


def test_numba_scenario_executes_compiled_updates() -> None:
    """The scenario exchanges built-in and extension messages through Numba."""
    results = _load_scenario().run()

    assert results["neutralDensity"] == pytest.approx([1.0e-11] * 3)
    assert results["localTemp"] == pytest.approx([275.0] * 3)
    assert results["statusDensity"] == pytest.approx([1.0e-11] * 3)
    assert results["statusScaleHeight"] == pytest.approx([8_500.0] * 3)
    assert results["statusModelValid"] == [1] * 3
    assert results["atmoTimes"] == [0, 500_000_000, 1_000_000_000]
    assert results["statusTimes"] == results["atmoTimes"]
    assert results["updateCount"] == 3
    assert results["lastUpdateNanos"] == 1_000_000_000
    assert results["moduleID"] >= 0
    assert results["lastModuleID"] == results["moduleID"]


def test_unlinked_custom_reader_uses_built_in_fallback() -> None:
    """The IsLinked guard permits an unconnected extension message reader."""
    results = _load_scenario().run(connect_custom_status=False)

    assert results["neutralDensity"] == pytest.approx([2.5e-12] * 3)
    assert results["statusDensity"] == pytest.approx([2.5e-12] * 3)
    assert results["statusScaleHeight"] == pytest.approx([0.0] * 3)
    assert results["statusModelValid"] == [0] * 3


def _reset_module():
    """Reset an installed module with its required built-in reader connected."""
    module = numbaAtmosphere.NumbaAtmosphere()
    source = bsk_messaging.AtmoPropsMsg().write(
        bsk_messaging.AtmoPropsMsgPayload()
    )
    module.atmoInMsg.subscribeTo(source)
    module._test_source = source
    module.Reset(0)
    return module


def test_repeated_simulation_initialization_reuses_compiled_function() -> None:
    """A second initialization reuses the cfunc and leaves message I/O valid."""
    simulation = SimulationBaseClass.SimBaseClass()
    process = simulation.CreateNewProcess("cacheProcess")
    task_period = macros.sec2nano(0.5)
    process.addTask(
        simulation.CreateNewTask("cacheTask", task_period)
    )
    first = numbaAtmosphere.NumbaAtmosphere()
    first.memory.densityScale = 3.0
    source_payload = bsk_messaging.AtmoPropsMsgPayload()
    source_payload.neutralDensity = 2.0e-12
    source_payload.localTemp = 280.0
    source = bsk_messaging.AtmoPropsMsg().write(source_payload)
    first.atmoInMsg.subscribeTo(source)
    recorder = first.atmoOutMsg.recorder()
    simulation.AddModelToTask("cacheTask", first)
    simulation.AddModelToTask("cacheTask", recorder)

    simulation.InitializeSimulation()
    compiled = first._cfunc
    simulation.InitializeSimulation()
    simulation.ConfigureStopTime(task_period)
    simulation.ExecuteSimulation()
    second = _reset_module()

    assert first._cfunc is compiled
    assert second._cfunc is compiled
    assert recorder.neutralDensity == pytest.approx([6.0e-12] * 2)
    assert recorder.localTemp == pytest.approx([280.0] * 2)
    assert list(recorder.times()) == [0, task_period]
    assert first.memory.updateCount == 2
    assert first.memory.lastUpdateNanos == task_period
    assert first.memory.lastModuleID == first.moduleID


def test_custom_payload_without_dtype_has_useful_failure(monkeypatch) -> None:
    """Unsupported generated payload layouts fail clearly during Reset."""
    monkeypatch.setattr(
        custom_atm.messaging.CustomAtmStatusMsgPayload, "__dtype__", None
    )

    with pytest.raises(TypeError, match=r"CustomAtmStatusMsgPayload.__dtype__ is None"):
        numbaAtmosphere.NumbaAtmosphere().Reset(0)
