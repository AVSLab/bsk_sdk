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

r"""
Overview
--------

Demonstrates dropping a Rust-backed BSK module into a standard attitude-control
simulation in place of an equivalent C++ module.

This is intentionally a **minimal pattern demo**, not a feature-complete
port of :ref:`scenarioAttitudeFeedback`. It reuses that scenario's spacecraft
dynamics, :ref:`simpleNav` sensor, :ref:`inertial3D` guidance, and
:ref:`attTrackingError` computation, but the controller itself only
implements the bare proportional-derivative law below — none of
:ref:`mrpFeedback`'s extra knobs (integral gain, feed-forward torque, the
C-vs-C++ message demo) are reproduced. Exercising those isn't the point:
the point is the wiring pattern for swapping in a Rust module.
``mrpRustController``'s ``SelfInit`` / ``Update`` / ``Reset`` lifecycle
functions are implemented in Rust and compiled to a static library that is
linked into the SWIG-generated Python extension.

For the full set of features the Rust module system supports (multiple
message ports, optional inputs, stateful modules, etc.), see the Basilisk
documentation's :ref:`writingRustPlugins` page rather than this example —
keeping the example minimal means it won't need to track every change to
the upstream :ref:`scenarioAttitudeFeedback` tutorial it borrows dynamics
from.

.. code-block:: text

    [spacecraft C++]
         |  scStateOutMsg
    [simpleNav C++]
         |  attOutMsg
    [attTrackingError C++] <-- [inertial3D C++]  attRefOutMsg
         |  attGuidOutMsg
    [mrpRustController **Rust**]          <- swap point
         |  cmdTorqueOutMsg
    [extForceTorque C++]

Because the Rust module implements the same proportional control law
:math:`\boldsymbol{\tau} = -K\,\boldsymbol{\sigma}_{BR}` and exposes
identical message ports, the wiring code is unchanged from the C++ version.

The script is found in the folder ``bsk_sdk/examples/rust-mrp-plugin`` and
executed by using::

    python3 scenarioAttitudeFeedbackRust.py

Running directly always displays plots (Basilisk convention).
Pass ``--no-plots`` to suppress the interactive window::

    python3 scenarioAttitudeFeedbackRust.py --no-plots

When the simulation completes, three plots are shown:

* MRP attitude error :math:`\boldsymbol{\sigma}_{B/R}`
* Rate tracking error :math:`\boldsymbol{\omega}_{B/R}`
* Control torque :math:`\boldsymbol{L}_r`

Illustration of Simulation Results
-----------------------------------

::

    show_plots = True, useUnmodeledTorque = False


.. image:: /_images/Scenarios/scenarioAttitudeFeedbackRust10.svg
   :align: center

.. image:: /_images/Scenarios/scenarioAttitudeFeedbackRust20.svg
   :align: center

"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np

from Basilisk.architecture import messaging
from Basilisk.fswAlgorithms import attTrackingError, inertial3D
from Basilisk.simulation import extForceTorque, simpleNav, spacecraft
from Basilisk.utilities import (
    SimulationBaseClass,
    macros,
    orbitalMotion,
    simHelpers,
    simIncludeGravBody,
    vizSupport,
)

# The Rust-backed attitude controller lives in mrpRustController/.
# Build with CMake (see README.md); the compiled .so and SWIG wrapper land
# in mrpRustController/ alongside the Rust source.
from mrpRustController import mrpRustController

fileName = os.path.basename(os.path.splitext(__file__)[0])


def run(show_plots, useUnmodeledTorque):
    r"""Set up and execute the attitude-feedback scenario with the Rust controller.

    :param show_plots: Set ``True`` to display matplotlib figures interactively.
    :param useUnmodeledTorque: Set ``True`` to apply a constant unmodeled disturbance
        torque :math:`[0.25,\,-0.25,\,0.1]` Nm.

    """
    simTaskName = "simTask"
    simProcessName = "simProcess"

    scSim = SimulationBaseClass.SimBaseClass()

    simulationTime = macros.min2nano(10.)  # [ns]

    dynProcess = scSim.CreateNewProcess(simProcessName)
    simulationTimeStep = macros.sec2nano(.1)  # [ns]
    dynProcess.addTask(scSim.CreateNewTask(simTaskName, simulationTimeStep))

    # -------------------------------------------------------------------------
    # Spacecraft dynamics
    # -------------------------------------------------------------------------
    scObject = spacecraft.Spacecraft()
    scObject.ModelTag = "spacecraftBody"

    I = [900., 0., 0.,
         0., 800., 0.,
         0., 0., 600.]  # [kg m^2]
    scObject.hub.mHub = 750.0  # [kg]
    scObject.hub.r_BcB_B = [[0.0], [0.0], [0.0]]  # [m]
    scObject.hub.IHubPntBc_B = simHelpers.np2EigenMatrix3d(I)
    scSim.AddModelToTask(simTaskName, scObject)

    gravFactory = simIncludeGravBody.gravBodyFactory()
    earth = gravFactory.createEarth()
    earth.isCentralBody = True
    mu = earth.mu
    gravFactory.addBodiesTo(scObject)

    extFTObject = extForceTorque.ExtForceTorque()
    extFTObject.ModelTag = "externalDisturbance"
    if useUnmodeledTorque:
        extFTObject.extTorquePntB_B = [[0.25], [-0.25], [0.1]]  # [Nm]
    scObject.addDynamicEffector(extFTObject)
    scSim.AddModelToTask(simTaskName, extFTObject)

    # -------------------------------------------------------------------------
    # Navigation sensor
    # -------------------------------------------------------------------------
    sNavObject = simpleNav.SimpleNav()
    sNavObject.ModelTag = "SimpleNavigation"
    scSim.AddModelToTask(simTaskName, sNavObject)

    # -------------------------------------------------------------------------
    # FSW: guidance reference + tracking error
    # -------------------------------------------------------------------------
    inertial3DObj = inertial3D.inertial3D()
    inertial3DObj.ModelTag = "inertial3D"
    inertial3DObj.sigma_R0N = [0., 0., 0.]  # [-] desired inertial orientation
    scSim.AddModelToTask(simTaskName, inertial3DObj)

    attError = attTrackingError.attTrackingError()
    attError.ModelTag = "attErrorInertial3D"
    scSim.AddModelToTask(simTaskName, attError)

    # -------------------------------------------------------------------------
    # FSW: Rust proportional MRP feedback controller
    #
    # This is the only module that differs from scenarioAttitudeFeedback.
    # mrpFeedback is replaced by mrpRustController, which exposes the same
    # attGuidInMsg input and cmdTorqueOutMsg output so the wiring below is
    # a drop-in replacement.
    # -------------------------------------------------------------------------
    rustCtrl = mrpRustController.mrpRustController()
    rustCtrl.ModelTag = "mrpRustController"
    rustCtrl.K = 3.5   # [Nm]
    rustCtrl.P = 30.0  # [Nm/(rad/s)]
    scSim.AddModelToTask(simTaskName, rustCtrl)

    # -------------------------------------------------------------------------
    # Connect messages
    # -------------------------------------------------------------------------
    sNavObject.scStateInMsg.subscribeTo(scObject.scStateOutMsg)
    attError.attNavInMsg.subscribeTo(sNavObject.attOutMsg)
    attError.attRefInMsg.subscribeTo(inertial3DObj.attRefOutMsg)
    rustCtrl.attGuidInMsg.subscribeTo(attError.attGuidOutMsg)
    extFTObject.cmdTorqueInMsg.subscribeTo(rustCtrl.cmdTorqueOutMsg)

    # -------------------------------------------------------------------------
    # Data logging
    # -------------------------------------------------------------------------
    numDataPoints = 100
    samplingTime = simHelpers.samplingTime(simulationTime, simulationTimeStep, numDataPoints)
    snLog = sNavObject.scStateInMsg.recorder(samplingTime)
    attErrLog = attError.attGuidOutMsg.recorder(samplingTime)
    mrpLog = rustCtrl.cmdTorqueOutMsg.recorder(samplingTime)
    scSim.AddModelToTask(simTaskName, snLog)
    scSim.AddModelToTask(simTaskName, attErrLog)
    scSim.AddModelToTask(simTaskName, mrpLog)

    # -------------------------------------------------------------------------
    # Initial spacecraft state
    # -------------------------------------------------------------------------
    oe = orbitalMotion.ClassicElements()
    oe.a = 10000000.0  # [m]
    oe.e = 0.01        # [-]
    oe.i = 33.3 * macros.D2R   # [rad]
    oe.Omega = 48.2 * macros.D2R  # [rad]
    oe.omega = 347.8 * macros.D2R  # [rad]
    oe.f = 85.3 * macros.D2R   # [rad]
    rN, vN = orbitalMotion.elem2rv(mu, oe)
    scObject.hub.r_CN_NInit = rN               # [m]
    scObject.hub.v_CN_NInit = vN               # [m/s]
    scObject.hub.sigma_BNInit = [[0.1], [0.2], [-0.3]]     # [-]  sigma_BN
    scObject.hub.omega_BN_BInit = [[0.001], [-0.01], [0.03]]  # [rad/s]

    # Uncomment to record a Vizard playback file:
    vizSupport.enableUnityVisualization(scSim, simTaskName, scObject
                                        # , saveFile=fileName
                                        )

    # -------------------------------------------------------------------------
    # Run
    # -------------------------------------------------------------------------
    scSim.InitializeSimulation()
    scSim.ConfigureStopTime(simulationTime)
    scSim.ExecuteSimulation()

    # -------------------------------------------------------------------------
    # Plots
    # -------------------------------------------------------------------------
    timeAxis = attErrLog.times()
    plt.close("all")

    plt.figure(1)
    for idx in range(3):
        plt.plot(timeAxis * macros.NANO2MIN, attErrLog.sigma_BR[:, idx],
                 color=simHelpers.getLineColor(idx, 3),
                 label=r'$\sigma_' + str(idx) + '$')
    plt.legend(loc='lower right')
    plt.xlabel('Time [min]')
    plt.ylabel(r'Attitude Error $\sigma_{B/R}$')
    figureList = {}
    pltName = fileName + "1" + str(int(useUnmodeledTorque))
    figureList[pltName] = plt.figure(1)

    plt.figure(2)
    for idx in range(3):
        plt.plot(timeAxis * macros.NANO2MIN, mrpLog.torqueRequestBody[:, idx],
                 color=simHelpers.getLineColor(idx, 3),
                 label='$L_{r,' + str(idx) + '}$')
    plt.legend(loc='lower right')
    plt.xlabel('Time [min]')
    plt.ylabel(r'Control Torque $L_r$ [Nm]')
    pltName = fileName + "2" + str(int(useUnmodeledTorque))
    figureList[pltName] = plt.figure(2)

    plt.figure(3)
    for idx in range(3):
        plt.plot(timeAxis * macros.NANO2MIN, attErrLog.omega_BR_B[:, idx],
                 color=simHelpers.getLineColor(idx, 3),
                 label=r'$\omega_{BR,' + str(idx) + '}$')
    plt.legend(loc='lower right')
    plt.xlabel('Time [min]')
    plt.ylabel('Rate Tracking Error [rad/s]')
    pltName = fileName + "3" + str(int(useUnmodeledTorque))
    figureList[pltName] = plt.figure(3)

    if show_plots:
        plt.show()
    plt.close("all")

    return figureList


if __name__ == "__main__":
    show_plots = "--no-plots" not in sys.argv
    run(
        show_plots=show_plots,
        useUnmodeledTorque=False,
    )
