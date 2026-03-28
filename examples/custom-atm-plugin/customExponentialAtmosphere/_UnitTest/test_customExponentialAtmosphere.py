"""
Integration test for the custom-atm-plugin example.

Requires:
  - bsk-sdk installed (provides the CMake helpers and SDK headers)
  - custom_atm wheel built and installed (see example-plugins/custom-atm-plugin)
  - Basilisk installed (provides SimulationBaseClass, messaging, etc.)

Skip gracefully if either optional dependency is absent so the smoke test
suite still passes in environments that only have bsk-sdk installed.
"""

from __future__ import annotations

import math

import pytest

basilisk = pytest.importorskip("Basilisk", reason="Basilisk not installed")
custom_atm = pytest.importorskip("custom_atm", reason="custom_atm plugin not installed")

from Basilisk.architecture import messaging, bskLogging  # noqa: E402
from Basilisk.utilities import SimulationBaseClass, macros  # noqa: E402
from custom_atm import customExponentialAtmosphere  # noqa: E402
from custom_atm.messaging import CustomAtmStatusMsg, CustomAtmStatusMsgPayload  # noqa: E402


def _window_density(log) -> float:
    vals = list(log.neutralDensity)
    assert vals, "No density samples were recorded"
    return float(max(vals))


@pytest.fixture()
def sim_env():
    """Set up a minimal Basilisk sim with the custom atmosphere plugin."""
    sim = SimulationBaseClass.SimBaseClass()
    sim.bskLogger.setLogLevel(bskLogging.BSK_WARNING)

    proc = sim.CreateNewProcess("proc")
    dt = macros.sec2nano(1.0)
    proc.addTask(sim.CreateNewTask("task", dt))

    atmosphere = customExponentialAtmosphere.CustomExponentialAtmosphere()
    atmosphere.planetRadius = 6_371_000.0  # m
    atmosphere.envMinReach = -1.0
    atmosphere.envMaxReach = -1.0
    atmosphere.baseDensity = 1.225          # kg/m^3
    atmosphere.scaleHeight = 8_500.0        # m
    atmosphere.localTemp = 293.0            # K

    sim.AddModelToTask("task", atmosphere)

    sc_pl = messaging.SCStatesMsgPayload()
    sc_pl.r_BN_N = [atmosphere.planetRadius + 400_000.0, 0.0, 0.0]
    sc_msg = messaging.SCStatesMsg()
    atmosphere.addSpacecraftToModel(sc_msg)
    sc_msg.write(sc_pl)
    # Keep Python message objects alive for the full fixture lifetime. If these
    # go out of scope, Basilisk can read them as unwritten/default and return
    # zero atmosphere outputs in tests.
    sim._test_sc_msg = sc_msg
    sim._test_sc_payload = sc_pl

    log = atmosphere.envOutMsgs[0].recorder()
    sim.AddModelToTask("task", log)

    sim.InitializeSimulation()
    # Re-write once after init so the subscriber is unambiguously marked written
    # for the first execution step across Basilisk/Python wrapper variations.
    sc_msg.write(sc_pl)
    return sim, atmosphere, log, dt


def test_plugin_instantiates():
    atm = customExponentialAtmosphere.CustomExponentialAtmosphere()
    assert atm is not None


def test_density_at_400km(sim_env):
    sim, atmosphere, log, dt = sim_env
    sim.ConfigureStopTime(dt)
    sim.ExecuteSimulation()

    rho = _window_density(log)
    # Analytic: rho = 1.225 * exp(-400e3 / 8500) ≈ 1.53e-23
    expected = 1.225 * math.exp(-400_000.0 / 8_500.0)
    assert rho == pytest.approx(expected, rel=1e-6, abs=0.0)


def test_density_positive(sim_env):
    sim, atmosphere, log, dt = sim_env
    sim.ConfigureStopTime(dt)
    sim.ExecuteSimulation()

    assert _window_density(log) > 0.0


def test_status_message_updates_density(sim_env):
    sim, atmosphere, log, dt = sim_env

    status_pl = CustomAtmStatusMsgPayload()
    status_pl.density = 2.0
    status_pl.scaleHeight = 8_500.0
    status_pl.modelValid = 1
    status_msg = CustomAtmStatusMsg().write(status_pl)
    atmosphere.connectAtmStatus(status_msg)

    sim.ConfigureStopTime(dt)
    sim.ExecuteSimulation()

    # With baseDensity overridden to 2.0, density should be ~2x the default
    rho = _window_density(log)
    expected = 2.0 * math.exp(-400_000.0 / 8_500.0)
    assert rho == pytest.approx(expected, rel=1e-6, abs=0.0)


def test_invalid_status_message_ignored(sim_env):
    sim, atmosphere, log, dt = sim_env

    # modelValid=0 — should be ignored, density stays at default baseDensity
    status_pl = CustomAtmStatusMsgPayload()
    status_pl.density = 999.0
    status_pl.scaleHeight = 1.0
    status_pl.modelValid = 0
    status_msg = CustomAtmStatusMsg().write(status_pl)
    atmosphere.connectAtmStatus(status_msg)

    sim.ConfigureStopTime(dt)
    sim.ExecuteSimulation()

    rho = _window_density(log)
    expected = 1.225 * math.exp(-400_000.0 / 8_500.0)
    assert rho == pytest.approx(expected, rel=1e-6, abs=0.0)


def test_recorder_grows_each_step(sim_env):
    sim, atmosphere, log, dt = sim_env

    for step in range(1, 4):
        sim.ConfigureStopTime(step * dt)
        sim.ExecuteSimulation()
        # Basilisk recorder writes an initial sample at sim initialization,
        # then one additional sample per executed step.
        assert len(log.neutralDensity) == step + 1
