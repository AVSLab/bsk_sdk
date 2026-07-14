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
#
#   Unit Test Script
#   Module Name:        scenarioAttitudeFeedbackRust
#   Creation Date:      July 2026
#
"""Regression test for the :ref:`scenarioAttitudeFeedbackRust` example.

Runs the full 10-minute attitude-feedback scenario with the Rust-backed
``mrpRustController`` and verifies convergence of the MRP attitude error
and rate tracking error.
"""

import pytest
import numpy as np


@pytest.mark.parametrize("useUnmodeledTorque", [False, True])
def test_scenarioAttitudeFeedbackRust(useUnmodeledTorque):
    r"""
    **Validation Test Description**

    Imports and executes :ref:`scenarioAttitudeFeedbackRust` with the
    ``useUnmodeledTorque`` flag both on and off.  For the noise-free case
    the MRP attitude error and rate tracking error must converge to zero
    within 10 minutes.  With an unmodeled disturbance the proportional-only
    controller cannot null the steady-state error, so only the simulation
    completion (no crash) is asserted.

    :param useUnmodeledTorque: Whether to inject a constant disturbance torque.
    :raises AssertionError: if the attitude error does not converge for the
        noise-free case.
    """
    import importlib.util, pathlib

    # Locate the scenario relative to this test file.
    scenarioPath = (
        pathlib.Path(__file__).resolve().parents[2]
        / "scenarioAttitudeFeedbackRust.py"
    )
    spec = importlib.util.spec_from_file_location("scenarioAttitudeFeedbackRust",
                                                   scenarioPath)
    scenario = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenario)

    figureList = scenario.run(False, useUnmodeledTorque)
    assert isinstance(figureList, dict), "scenario.run() must return a figure dict"

    if not useUnmodeledTorque:
        # Re-run with data logging to check convergence numerically.
        from Basilisk.architecture import messaging
        from Basilisk.fswAlgorithms import attTrackingError, inertial3D
        from Basilisk.simulation import extForceTorque, simpleNav, spacecraft
        from Basilisk.utilities import (
            SimulationBaseClass,
            macros,
            orbitalMotion,
            simHelpers,
            simIncludeGravBody,
        )
        from mrpRustController import mrpRustController

        scSim = SimulationBaseClass.SimBaseClass()
        simTask = "simTask"
        dynProc = scSim.CreateNewProcess("simProc")
        dt = macros.sec2nano(0.1)  # [ns]
        dynProc.addTask(scSim.CreateNewTask(simTask, dt))

        scObject = spacecraft.Spacecraft()
        scObject.ModelTag = "sc"
        I = [900., 0., 0., 0., 800., 0., 0., 0., 600.]  # [kg m^2]
        scObject.hub.mHub = 750.0  # [kg]
        scObject.hub.r_BcB_B = [[0.], [0.], [0.]]
        scObject.hub.IHubPntBc_B = simHelpers.np2EigenMatrix3d(I)
        scSim.AddModelToTask(simTask, scObject)

        gravFactory = simIncludeGravBody.gravBodyFactory()
        earth = gravFactory.createEarth()
        earth.isCentralBody = True
        mu = earth.mu
        gravFactory.addBodiesTo(scObject)

        extFT = extForceTorque.ExtForceTorque()
        extFT.ModelTag = "extFT"
        scObject.addDynamicEffector(extFT)
        scSim.AddModelToTask(simTask, extFT)

        sNav = simpleNav.SimpleNav()
        sNav.ModelTag = "sNav"
        scSim.AddModelToTask(simTask, sNav)

        inertial3DObj = inertial3D.inertial3D()
        inertial3DObj.ModelTag = "inertial3D"
        inertial3DObj.sigma_R0N = [0., 0., 0.]
        scSim.AddModelToTask(simTask, inertial3DObj)

        attErr = attTrackingError.attTrackingError()
        attErr.ModelTag = "attErr"
        scSim.AddModelToTask(simTask, attErr)

        rustCtrl = mrpRustController.mrpRustController()
        rustCtrl.ModelTag = "rustCtrl"
        rustCtrl.K = 3.5   # [Nm]
        rustCtrl.P = 30.0  # [Nm/(rad/s)]
        scSim.AddModelToTask(simTask, rustCtrl)

        sNav.scStateInMsg.subscribeTo(scObject.scStateOutMsg)
        attErr.attNavInMsg.subscribeTo(sNav.attOutMsg)
        attErr.attRefInMsg.subscribeTo(inertial3DObj.attRefOutMsg)
        rustCtrl.attGuidInMsg.subscribeTo(attErr.attGuidOutMsg)
        extFT.cmdTorqueInMsg.subscribeTo(rustCtrl.cmdTorqueOutMsg)

        simulationTime = macros.min2nano(10.)  # [ns]
        attErrLog = attErr.attGuidOutMsg.recorder(macros.sec2nano(1.))
        scSim.AddModelToTask(simTask, attErrLog)

        oe = orbitalMotion.ClassicElements()
        oe.a = 10000000.0  # [m]
        oe.e = 0.01
        oe.i = 33.3 * macros.D2R
        oe.Omega = 48.2 * macros.D2R
        oe.omega = 347.8 * macros.D2R
        oe.f = 85.3 * macros.D2R
        rN, vN = orbitalMotion.elem2rv(mu, oe)
        scObject.hub.r_CN_NInit = rN
        scObject.hub.v_CN_NInit = vN
        scObject.hub.sigma_BNInit = [[0.1], [0.2], [-0.3]]
        scObject.hub.omega_BN_BInit = [[0.001], [-0.01], [0.03]]

        scSim.InitializeSimulation()
        scSim.ConfigureStopTime(simulationTime)
        scSim.ExecuteSimulation()

        sigma_final = attErrLog.sigma_BR[-1]   # [-]
        omega_final = attErrLog.omega_BR_B[-1]  # [rad/s]

        np.testing.assert_allclose(
            sigma_final, [0., 0., 0.],
            atol=1e-2,
            err_msg="Attitude error did not converge to zero within 10 min",
        )
        np.testing.assert_allclose(
            omega_final, [0., 0., 0.],
            atol=1e-4,
            err_msg="Rate error did not converge to zero within 10 min",
        )


if __name__ == "__main__":
    test_scenarioAttitudeFeedbackRust(False)
    test_scenarioAttitudeFeedbackRust(True)
