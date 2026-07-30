// ISC License
//
// Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
//
// Permission to use, copy, modify, and/or distribute this software for any
// purpose with or without fee is hereby granted, provided that the above
// copyright notice and this permission notice appear in all copies.
//
// THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
// WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
// MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
// ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
// WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
// ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
// OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

//! Rust module built into the custom-atmosphere extension wheel.

#![allow(non_snake_case)]

use bsk_messages::*;

/// Atmosphere scaling configuration and message ports.
#[bsk_build::module]
#[repr(C)]
pub struct RustAtmosphereConfig {
    /// [-] Multiplicative atmospheric density scale factor
    #[bsk(validate = validate_density_scale)]
    pub densityScale: f64,
    /// [-] Required built-in Basilisk atmosphere input
    pub atmoInMsg: MsgReader<AtmoPropsMsg>,
    /// [-] Optional extension-defined atmosphere status input
    #[bsk(optional)]
    pub statusInMsg: MsgReader<CustomAtmStatusMsg>,
    /// [-] Built-in Basilisk atmosphere output
    pub atmoOutMsg: MsgWriter<AtmoPropsMsg>,
    /// [-] Extension-defined atmosphere status output
    pub statusOutMsg: MsgWriter<CustomAtmStatusMsg>,
}

/// Private Rust state that never crosses the extension ABI.
#[derive(Default)]
pub struct RustAtmosphereState {
    /// [-] Number of completed update calls
    update_count: u64,
}

/// Reject invalid density scales before changing the module configuration.
fn validate_density_scale(_config: &RustAtmosphereConfig, density_scale: &f64) -> BskResult<()> {
    if !density_scale.is_finite() || *density_scale < 0.0 {
        return Err(BskError::new(
            "rustAtmosphere.densityScale must be finite and non-negative",
        ));
    }
    Ok(())
}

impl BskModule for RustAtmosphereConfig {
    type State = RustAtmosphereState;
    type Inputs = RustAtmosphereInputs;
    type Outputs = RustAtmosphereOutputs;

    fn init(&mut self, _state: &mut Self::State) -> BskResult<()> {
        self.densityScale = 1.0; // [-]
        Ok(())
    }

    fn reset(
        &mut self,
        state: &mut Self::State,
        _context: &BskContext<'_>,
        _current_sim_nanos: u64,
    ) -> BskResult<Self::Outputs> {
        validate_density_scale(self, &self.densityScale)?;
        state.update_count = 0;
        Ok(RustAtmosphereOutputs::default())
    }

    fn update(
        &mut self,
        state: &mut Self::State,
        _context: &BskContext<'_>,
        inputs: Self::Inputs,
        _current_sim_nanos: u64,
    ) -> BskResult<Self::Outputs> {
        let mut atmosphere = inputs.atmoInMsg;
        let default_scale_height = 0.0; // [m]
        let (source_density, scale_height, model_valid) = inputs
            .statusInMsg
            .filter(|status| status.modelValid != 0)
            .map_or(
                (atmosphere.neutralDensity, default_scale_height, 0),
                |status| (status.density, status.scaleHeight, 1),
            );
        let scaled_density = source_density * self.densityScale;
        atmosphere.neutralDensity = scaled_density;
        state.update_count += 1;

        let status = CustomAtmStatusMsg {
            density: scaled_density,
            scaleHeight: scale_height,
            modelValid: model_valid,
        };
        Ok(RustAtmosphereOutputs {
            atmoOutMsg: Some(atmosphere),
            statusOutMsg: Some(status),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_density_scale() {
        let config = RustAtmosphereConfig {
            densityScale: 1.0, // [-]
            atmoInMsg: MsgReader::default(),
            statusInMsg: MsgReader::default(),
            atmoOutMsg: MsgWriter::default(),
            statusOutMsg: MsgWriter::default(),
        };
        assert!(validate_density_scale(&config, &0.0).is_ok());
        assert!(validate_density_scale(&config, &2.5).is_ok());
        assert!(validate_density_scale(&config, &-1.0).is_err());
        assert!(validate_density_scale(&config, &f64::NAN).is_err());
    }
}
