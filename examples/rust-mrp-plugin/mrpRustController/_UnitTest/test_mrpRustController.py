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
#   Module Name:        mrpRustController
#   Creation Date:      July 2026
#
"""Unit test for the mrpRustController Basilisk module.

Verifies the proportional-derivative MRP control law:

.. math::

    \\boldsymbol{\\tau} = -K \\, \\boldsymbol{\\sigma}_{BR} - P \\, \\boldsymbol{\\omega}_{BR}

by injecting known attitude errors and checking the output torque.
"""

import numpy as np
import pytest
from Basilisk.architecture import bskLogging, messaging
from Basilisk.utilities import SimulationBaseClass, macros


def test_mrpRustController_proportionalLaw():
    r"""
    **Validation Test Description**

    Injects a known MRP attitude error :math:`\boldsymbol{\sigma}_{BR}` and rate
    error :math:`\boldsymbol{\omega}_{BR}` into the ``mrpRustController`` module and
    verifies that the commanded torque equals
    :math:`\boldsymbol{\tau} = -K\,\boldsymbol{\sigma}_{BR} - P\,\boldsymbol{\omega}_{BR}`
    to within floating-point precision.

    **Test Parameters**

    - Proportional gain: :math:`K = 5` [Nm]
    - Rate gain: :math:`P = 10` [Nm/(rad/s)]
    - Input :math:`\boldsymbol{\sigma}_{BR} = [0.1,\ -0.2,\ 0.3]` [-]
    - Input :math:`\boldsymbol{\omega}_{BR} = [0.01,\ -0.02,\ 0.03]` [rad/s]
    - Expected: :math:`\boldsymbol{\tau} = -K\sigma_{BR} - P\omega_{BR}` [Nm]

    :raises AssertionError: if the computed torque does not match the expected value.
    """
    from mrpRustController import mrpRustController

    unitSim = SimulationBaseClass.SimBaseClass()
    unitProc = unitSim.CreateNewProcess("testProc")
    unitTask = unitSim.CreateNewTask("testTask", macros.sec2nano(0.1))  # [ns]
    unitProc.addTask(unitTask)

    ctrl = mrpRustController.mrpRustController()
    ctrl.ModelTag = "rustMRP"
    unitSim.AddModelToTask("testTask", ctrl)

    K = 5.0   # [Nm]
    P = 10.0  # [Nm/(rad/s)]
    ctrl.K = K
    ctrl.P = P

    sigma_BR = np.array([0.1, -0.2, 0.3])     # [-]
    omega_BR = np.array([0.01, -0.02, 0.03])   # [rad/s]
    attGuidIn = messaging.AttGuidMsgPayload()
    attGuidIn.sigma_BR = sigma_BR
    attGuidIn.omega_BR_B = omega_BR
    attGuidMsg = messaging.AttGuidMsg()
    attGuidMsg.write(attGuidIn)
    ctrl.attGuidInMsg.subscribeTo(attGuidMsg)

    unitSim.InitializeSimulation()
    unitSim.TotalSim.SingleStepProcesses()

    torqueOut = ctrl.cmdTorqueOutMsg.read()
    expected = -K * sigma_BR - P * omega_BR  # [Nm]

    np.testing.assert_allclose(
        torqueOut.torqueRequestBody,
        expected,
        rtol=1e-12,
    )


def test_mrpRustController_zeroError():
    r"""
    **Validation Test Description**

    Verifies that a zero attitude error :math:`\boldsymbol{\sigma}_{BR} = \mathbf{0}`
    produces a zero torque command regardless of the gain :math:`K`.

    :raises AssertionError: if the output torque is non-zero for zero attitude error.
    """
    from mrpRustController import mrpRustController

    unitSim = SimulationBaseClass.SimBaseClass()
    unitProc = unitSim.CreateNewProcess("testProc2")
    unitTask = unitSim.CreateNewTask("testTask2", macros.sec2nano(0.1))  # [ns]
    unitProc.addTask(unitTask)

    ctrl = mrpRustController.mrpRustController()
    ctrl.ModelTag = "rustMRP_zero"
    unitSim.AddModelToTask("testTask2", ctrl)

    ctrl.K = 10.0  # [Nm]

    attGuidIn = messaging.AttGuidMsgPayload()
    attGuidIn.sigma_BR = [0.0, 0.0, 0.0]  # [-]
    attGuidMsg = messaging.AttGuidMsg()
    attGuidMsg.write(attGuidIn)
    ctrl.attGuidInMsg.subscribeTo(attGuidMsg)

    unitSim.InitializeSimulation()
    unitSim.TotalSim.SingleStepProcesses()

    torqueOut = ctrl.cmdTorqueOutMsg.read()
    np.testing.assert_allclose(
        torqueOut.torqueRequestBody,
        [0.0, 0.0, 0.0],  # [Nm]
        atol=1e-15,
    )


def test_mrpRustController_unlinkedRequiredInput():
    r"""
    **Validation Test Description**

    Verifies that an unconnected required input raises the standard
    ``BasiliskError`` before the generated shim can dereference a null message
    header.

    """
    from mrpRustController import mrpRustController

    unitSim = SimulationBaseClass.SimBaseClass()
    unitProc = unitSim.CreateNewProcess("testProc3")
    unitTask = unitSim.CreateNewTask("testTask3", macros.sec2nano(0.1))  # [ns]
    unitProc.addTask(unitTask)

    ctrl = mrpRustController.mrpRustController()
    ctrl.ModelTag = "rustMRP_unlinked"
    unitSim.AddModelToTask("testTask3", ctrl)

    with pytest.raises(bskLogging.BasiliskError, match="attGuidInMsg is not connected"):
        unitSim.InitializeSimulation()


def test_mrpRustController_nonPositiveGainWarning(capfd):
    r"""
    **Validation Test Description**

    Verifies that ``Reset`` logs a standard ``BSK_WARNING`` (via
    ``BskLoggerExt``, not the auto-generated required-input check) for a
    non-positive gain, exercising the general-purpose Rust logging path
    described in the Basilisk documentation's "Writing a Rust Plugin" page.
    A warning is non-fatal, so this checks the printed log line (``BSKLogger``
    writes to stdout) rather than an exception.

    """
    from mrpRustController import mrpRustController

    unitSim = SimulationBaseClass.SimBaseClass()
    unitProc = unitSim.CreateNewProcess("testProc4")
    unitTask = unitSim.CreateNewTask("testTask4", macros.sec2nano(0.1))  # [ns]
    unitProc.addTask(unitTask)

    ctrl = mrpRustController.mrpRustController()
    ctrl.ModelTag = "rustMRP_badGain"
    ctrl.K = 0.0  # [Nm] intentionally invalid — should trigger a warning, not a fatal error
    ctrl.P = 10.0  # [Nm/(rad/s)]
    attGuidMsg = messaging.AttGuidMsg()
    attGuidMsg.write(messaging.AttGuidMsgPayload())
    ctrl.attGuidInMsg.subscribeTo(attGuidMsg)
    unitSim.AddModelToTask("testTask4", ctrl)

    unitSim.InitializeSimulation()

    captured = capfd.readouterr()
    assert "non-positive gain" in captured.out


if __name__ == "__main__":
    test_mrpRustController_proportionalLaw()
    test_mrpRustController_zeroError()
    test_mrpRustController_unlinkedRequiredInput()
