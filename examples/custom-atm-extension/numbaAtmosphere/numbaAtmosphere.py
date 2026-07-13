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

"""Numba-compiled atmosphere module for the BSK-SDK extension example.

See https://avslab.github.io/basilisk/Learn/makingModules/numbaModules.html
for the complete Basilisk Numba module API and its nopython-mode constraints.
"""

from Basilisk.architecture import messaging as bsk_messaging
from Basilisk.architecture.numbaModel import NumbaModel

from . import messaging as extension_messaging


class NumbaAtmosphere(NumbaModel):
    """Scale atmospheric density in a Numba-compiled update function."""

    def __init__(self) -> None:
        """Declare message interfaces and persistent module memory."""
        super().__init__()
        self.atmoInMsg = bsk_messaging.AtmoPropsMsgReader()
        self.statusInMsg = extension_messaging.CustomAtmStatusMsgReader()
        self.atmoOutMsg = bsk_messaging.AtmoPropsMsg()
        self.statusOutMsg = extension_messaging.CustomAtmStatusMsg()
        self.memory.densityScale = 1.0  # [-]
        self.memory.updateCount = 0
        self.memory.lastUpdateNanos = 0
        self.memory.lastModuleID = -1

    @staticmethod
    def UpdateStateImpl(
        atmoInMsgPayload,
        statusInMsgPayload,
        statusInMsgIsLinked,
        atmoOutMsgPayload,
        statusOutMsgPayload,
        CurrentSimNanos,
        moduleID,
        memory,
    ) -> None:
        """Scale density and publish built-in and extension message outputs."""
        source_density = atmoInMsgPayload.neutralDensity
        scale_height = 0.0
        model_valid = 0
        if statusInMsgIsLinked:
            scale_height = statusInMsgPayload.scaleHeight
            if statusInMsgPayload.modelValid:
                source_density = statusInMsgPayload.density
                model_valid = 1

        scaled_density = source_density * memory.densityScale
        atmoOutMsgPayload.neutralDensity = scaled_density
        atmoOutMsgPayload.localTemp = atmoInMsgPayload.localTemp

        statusOutMsgPayload.density = scaled_density
        statusOutMsgPayload.scaleHeight = scale_height
        statusOutMsgPayload.modelValid = model_valid

        memory.updateCount += 1
        memory.lastUpdateNanos = CurrentSimNanos
        memory.lastModuleID = moduleID
