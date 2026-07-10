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

#pragma once

#include "simulation/environment/_GeneralModuleFiles/atmosphereBase.h"
#include "architecture/utilities/bskLogging.h"
#include "architecture/messaging/messaging.h"   // ReadFunctor / Message
#include "CustomAtmStatusMsgPayload.h"

/*! @brief exponential atmosphere model (extension example) */
class CustomExponentialAtmosphere : public AtmosphereBase
{
public:
    CustomExponentialAtmosphere();
    ~CustomExponentialAtmosphere();

    // Extension-defined input message wiring (idiomatic Basilisk pattern)
    void connectAtmStatus(Message<CustomAtmStatusMsgPayload>* msg);

    /*! @brief Compute the orbital radius for a circular orbit using Basilisk's orbitalMotion utility.
     *
     * This helper exists to exercise a Basilisk architecture utility from the
     * extension example. It proves that extension modules can include
     * architecture/utilities/orbitalMotion.h and link against the corresponding
     * SDK-provided utility implementation.
     *
     * @param mu [m^3/s^2] Gravitational parameter used by elem2rv()
     * @param semiMajorAxis [m] Circular orbit semi-major axis
     * @return [m] Euclidean norm of the position vector returned by elem2rv()
     */
    double radiusFromCircularElements(double mu, double semiMajorAxis);

private:
    void evaluateAtmosphereModel(AtmoPropsMsgPayload* msg, double currentTime) override;

    ReadFunctor<CustomAtmStatusMsgPayload> atmStatusInMsg_;

public:
    double baseDensity;            //!< [kg/m^3] Density at h=0
    double scaleHeight;            //!< [m] Exponential characteristic height
    double localTemp = 293.0;      //!< [K] Local atmospheric temperature (constant)
    BSKLogger bskLogger;           //!< -- BSK Logging
};
