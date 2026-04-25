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


#include "customExponentialAtmosphere.h"

#include "architecture/utilities/orbitalMotion.h"

#include <cmath>

/*! The constructor method initializes the dipole parameters to zero, resuling in a zero magnetic field result by default.

 */
CustomExponentialAtmosphere::CustomExponentialAtmosphere()
{
    //! - Set the default atmospheric properties to yield a zero response
    this->baseDensity = 0.0;            // [T]
    this->scaleHeight = 1.0;            // [m]
    this->planetRadius = 0.0;   // [m]
    this->localTemp = 1.0; // [K]

    return;
}

/*! Empty destructor method.

 */
CustomExponentialAtmosphere::~CustomExponentialAtmosphere()
{
    return;
}

/*! This method is evaluates the centered dipole magnetic field model.
 @param msg magnetic field message structure
 @param currentTime current time (s)

 */
void CustomExponentialAtmosphere::evaluateAtmosphereModel(AtmoPropsMsgPayload* msg, double currentTime)
{
    (void)currentTime;

    static bool firstCall = true;
    if (firstCall) {
        this->bskLogger.bskLog(BSK_INFORMATION,
            "ExponentialAtmosphere (plugin): model active; using AtmosphereBase altitude.");
        firstCall = false;
    }

    bool statusApplied = false;
    if (this->atmStatusInMsg_.isLinked()) {
        const CustomAtmStatusMsgPayload status = this->atmStatusInMsg_(); // payload copy
        if (status.modelValid) {
            this->baseDensity = status.density;
            this->scaleHeight = status.scaleHeight;
            statusApplied = true;
        } else {
            this->bskLogger.bskLog(BSK_WARNING,
                "ExponentialAtmosphere (plugin): CustomAtmStatusMsgPayload invalid; ignoring.");
        }
    }

    const double exponent = -(this->orbitAltitude) / this->scaleHeight;
    msg->neutralDensity = this->baseDensity * std::exp(exponent);
    msg->localTemp      = this->localTemp;

    if (statusApplied) {
        this->bskLogger.bskLog(BSK_INFORMATION,
            "ExponentialAtmosphere (plugin): applied status msg; alt=%.3g m rho=%.3g",
            this->orbitAltitude, msg->neutralDensity);
    }
}

void CustomExponentialAtmosphere::connectAtmStatus(Message<CustomAtmStatusMsgPayload>* msg)
{
    this->atmStatusInMsg_.subscribeTo(msg);
}

/*! Compute a circular-orbit radius using Basilisk's orbitalMotion utility.
 @param mu gravitational parameter passed to elem2rv() in m^3/s^2
 @param semiMajorAxis circular orbit semi-major axis in meters
 @return position-vector magnitude returned by elem2rv() in meters
 */
double CustomExponentialAtmosphere::radiusFromCircularElements(double mu, double semiMajorAxis)
{
    //! - Define a simple circular orbit in the inertial reference plane.
    ClassicElements elements = {};  //!< -- Classic orbit elements consumed by elem2rv()
    elements.a = semiMajorAxis;     // [m] Semi-major axis
    elements.e = 0.0;               // -- Circular orbit eccentricity
    elements.i = 0.0;               // [rad] Orbit inclination
    elements.Omega = 0.0;           // [rad] Right ascension of ascending node
    elements.omega = 0.0;           // [rad] Argument of periapsis
    elements.f = 0.0;               // [rad] True anomaly

    //! - Convert the orbital elements to position and velocity with orbitalMotion.
    double rVec[3] = {};            //!< [m] Inertial position vector
    double vVec[3] = {};            //!< [m/s] Inertial velocity vector

    elem2rv(mu, &elements, rVec, vVec);

    //! - Return the position magnitude so the Python test can verify the call.
    return std::sqrt(rVec[0] * rVec[0] + rVec[1] * rVec[1] + rVec[2] * rVec[2]);
}
