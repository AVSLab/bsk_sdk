/*
 ISC License

 Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder

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

/*
 * Minimal C module that uses the plugin's built-in planet-state input message
 * through the C interface shipped by bsk-sdk.
 */
#ifndef PLANET_STATE_PROBE_H
#define PLANET_STATE_PROBE_H

#ifdef __cplusplus
extern "C" {
#endif

/*! Round-trip a position through a SpicePlanetStateMsg using only the
 *  SDK-shipped C message interface. Returns PositionVector[0] read
 *  back from the message, which equals positionX when the interface works. */
double roundTripPlanetPosition(double positionX);

#ifdef __cplusplus
}
#endif

#endif
