/*
 ISC License

 Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at
 Boulder

 Permission to use, copy, modify, and/or distribute this software for any
 purpose with or without fee is hereby granted, provided that the above
 copyright notice and this permission notice appear in all copies.

 THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

 */

#include "planetStateProbe.h"

#include <string.h>

#include "cMsgCInterface/SpicePlanetStateMsg_C.h"

double roundTripPlanetPosition(double positionX) {
  /*
   * Zero the container so _init() connects the message to itself instead of
   * dereferencing an uninitialized payload pointer.
   */
  SpicePlanetStateMsg_C planetMsg;
  memset(&planetMsg, 0, sizeof(planetMsg));
  SpicePlanetStateMsg_C_init(&planetMsg);

  SpicePlanetStateMsgPayload payload = SpicePlanetStateMsg_C_zeroMsgPayload();
  payload.PositionVector[0] = positionX;
  SpicePlanetStateMsg_C_write(&payload, &planetMsg, 0, 0);

  SpicePlanetStateMsgPayload readBack = SpicePlanetStateMsg_C_read(&planetMsg);
  return readBack.PositionVector[0];
}
