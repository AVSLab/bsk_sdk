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

CustomExponentialAtmosphere::CustomExponentialAtmosphere() = default;

/*! Reset the extension-specific model state. */
void CustomExponentialAtmosphere::customReset(uint64_t currentSimNanos)
{
    (void) currentSimNanos;
    this->invalidStatusWarningIssued = false;
    this->bskLogger.bskLog(
        BSK_INFORMATION,
        "CustomExponentialAtmosphere initialized with base density %.3g kg/m^3 "
        "and scale height %.3g m.",
        this->baseDensity,
        this->scaleHeight);
}

/*! Evaluate the exponential atmosphere at the current spacecraft altitude. */
void CustomExponentialAtmosphere::evaluateAtmosphereModel(AtmoPropsMsgPayload *msg, double currentTime)
{
    (void) currentTime;

    if (this->atmStatusInMsg.isLinked()) {
        const CustomAtmStatusMsgPayload status = this->atmStatusInMsg();
        if (status.modelValid) {
            this->baseDensity = status.density;
            this->scaleHeight = status.scaleHeight;
            this->invalidStatusWarningIssued = false;
        } else if (!this->invalidStatusWarningIssued) {
            this->bskLogger.bskLog(
                BSK_WARNING,
                "%s",
                "CustomExponentialAtmosphere received an invalid status message; "
                "retaining the configured parameters.");
            this->invalidStatusWarningIssued = true;
        }
    }

    if (!std::isfinite(this->baseDensity) || this->baseDensity < 0.0) {
        this->bskLogger.bskError(
            "CustomExponentialAtmosphere.baseDensity must be finite and non-negative.");
    }
    if (!std::isfinite(this->scaleHeight) || this->scaleHeight <= 0.0) {
        this->bskLogger.bskError(
            "CustomExponentialAtmosphere.scaleHeight must be finite and positive.");
    }
    if (!std::isfinite(this->localTemp) || this->localTemp < 0.0) {
        this->bskLogger.bskError(
            "CustomExponentialAtmosphere.localTemp must be finite and non-negative.");
    }

    const double exponent = -(this->orbitAltitude) / this->scaleHeight;
    msg->neutralDensity = this->baseDensity * std::exp(exponent);
    msg->localTemp      = this->localTemp;
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
