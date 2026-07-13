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

"""Run the Numba module installed by the custom atmosphere extension wheel.

See https://avslab.github.io/basilisk/Learn/makingModules/numbaModules.html
for more information on making Numba Basilisk modules.
"""

from Basilisk.architecture import messaging
from Basilisk.utilities import SimulationBaseClass, macros
from custom_atm import messaging as custom_atm_messaging
from custom_atm import numbaAtmosphere


def run(*, connect_custom_status: bool = True) -> dict[str, object]:
    """Execute three compiled updates and return both message recordings."""
    simulation = SimulationBaseClass.SimBaseClass()
    process = simulation.CreateNewProcess("numbaProcess")
    task_period = macros.sec2nano(0.5)  # [ns]
    process.addTask(simulation.CreateNewTask("numbaTask", task_period))

    module = numbaAtmosphere.NumbaAtmosphere()
    module.ModelTag = "extensionNumbaAtmosphere"
    module.memory.densityScale = 2.5  # [-]

    source_payload = messaging.AtmoPropsMsgPayload()
    source_payload.neutralDensity = 1.0e-12  # [kg/m^3]
    source_payload.localTemp = 275.0  # [K]
    source_message = messaging.AtmoPropsMsg().write(source_payload)
    module.atmoInMsg.subscribeTo(source_message)

    if connect_custom_status:
        status_payload = custom_atm_messaging.CustomAtmStatusMsgPayload()
        status_payload.density = 4.0e-12  # [kg/m^3]
        status_payload.scaleHeight = 8_500.0  # [m]
        status_payload.modelValid = 1
        status_message = custom_atm_messaging.CustomAtmStatusMsg().write(status_payload)
        module.statusInMsg.subscribeTo(status_message)

    atmo_recorder = module.atmoOutMsg.recorder()
    status_recorder = module.statusOutMsg.recorder()
    simulation.AddModelToTask("numbaTask", module)
    simulation.AddModelToTask("numbaTask", atmo_recorder)
    simulation.AddModelToTask("numbaTask", status_recorder)

    simulation.InitializeSimulation()
    simulation.ConfigureStopTime(2 * task_period)
    simulation.ExecuteSimulation()

    return {
        "neutralDensity": list(atmo_recorder.neutralDensity),
        "localTemp": list(atmo_recorder.localTemp),
        "statusDensity": list(status_recorder.density),
        "statusScaleHeight": list(status_recorder.scaleHeight),
        "statusModelValid": list(status_recorder.modelValid),
        "atmoTimes": [int(value) for value in atmo_recorder.times()],
        "statusTimes": [int(value) for value in status_recorder.times()],
        "updateCount": int(module.memory.updateCount),
        "lastUpdateNanos": int(module.memory.lastUpdateNanos),
        "moduleID": int(module.moduleID),
        "lastModuleID": int(module.memory.lastModuleID),
    }


if __name__ == "__main__":
    results = run()
    print("scaled density [kg/m^3]:", results["neutralDensity"][-1])
    print("custom status density [kg/m^3]:", results["statusDensity"][-1])
    print("temperature [K]:", results["localTemp"][-1])
    print("compiled updates:", results["updateCount"])
