//  ISC License
//
//  Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
//
//  Permission to use, copy, modify, and/or distribute this software for any
//  purpose with or without fee is hereby granted, provided that the above
//  copyright notice and this permission notice appear in all copies.

//! MRP proportional-derivative attitude controller — Basilisk module in Rust.
//!
//! Implements :math:`\boldsymbol{\tau} = -K\,\boldsymbol{\sigma}_{BR} - P\,\boldsymbol{\omega}_{BR} - \boldsymbol{L}_{ff}`,
//! where :math:`\boldsymbol{L}_{ff}` is an optional feed-forward torque
//! estimate (zero when ``feedforwardTorqueInMsg`` is unconnected). This
//! optional port doubles as a worked example of an ``Option<Msg>`` input —
//! see ``type Inputs`` below and the Basilisk documentation's "Writing a
//! Rust Plugin" page (Messaging section).
//!
//! # Config struct as source of truth
//!
//! ``mrpRustControllerConfig`` is defined here in Rust with ``#[repr(C)]``.
//! ``build.rs`` reads this file and automatically generates:
//!
//! * ``mrpRustController.h`` — C header for CMake/SWIG, generated in the build
//!   tree.
//! * ``bsk_shim.rs`` — ``Init`` / ``Reset`` / ``Update`` entry points that
//!   handle all message I/O and call the functions below.
//!
//! # Testing without Basilisk
//!
//! The ``update`` function is pure Rust.  Run ``cargo test`` in this directory
//! to exercise it without any Basilisk headers or libraries:
//!
//! ```text
//! cargo test
//! ```

#![allow(non_snake_case)]

use bsk_messages::*;

// ---------------------------------------------------------------------------
// Config struct — source of truth for the C header
//
// bsk-build (build.rs) uses syn to parse this struct's AST and generates:
//   • mrpRustController.h  — C typedef for CMake/SWIG in the build tree
//   • bsk_shim.rs          — Init/Reset/Update extern "C" entry points
//
// Use `///` doc comments; they are visible to syn and become Doxygen
// /*!< … */ comments in the generated C header.
// MsgReader/MsgWriter fields (see attGuidInMsg/cmdTorqueOutMsg below) are
// auto-wired as message ports. Whether a port is required or optional comes
// from the `impl BskModule` block below: wrap the matching `Inputs` tuple
// element in `Option<..>` to make it optional (see `type Inputs` further
// down).
// ---------------------------------------------------------------------------

/// Config struct for the MRP PD controller.
///
/// This is the single declaration that drives everything: build.rs reads it
/// to produce both the C header (for SWIG) and the BSK lifecycle shim.
#[repr(C)]
pub struct mrpRustControllerConfig {
    /// [-] SysModel runtime mirror (moduleID, ModelTag, CallCounts, RNGSeed);
    /// refreshed by the shim before every call, read like any other field
    pub runtime: BskModuleRuntime,
    /// [Nm] MRP proportional gain
    pub K: f64,
    /// [Nm/(rad/s)] rate (derivative) gain
    pub P: f64,
    /// [-] attitude guidance input
    pub attGuidInMsg: MsgReader<AttGuidMsg>,
    /// [Nm] optional feed-forward disturbance-torque estimate; see
    /// `type Inputs` below for how this is wired up as optional
    pub feedforwardTorqueInMsg: MsgReader<CmdTorqueBodyMsg>,
    /// [Nm] commanded torque output
    pub cmdTorqueOutMsg: MsgWriter<CmdTorqueBodyMsg>,
    /// [-] BSK logging handle
    pub bskLogger: *mut BSKLogger,
}

// ---------------------------------------------------------------------------
// Lifecycle shim — only compiled when linking into Basilisk (not cargo test).
// ---------------------------------------------------------------------------

#[cfg(not(test))]
bsk_build::bsk_module!();

// ---------------------------------------------------------------------------
// Strongly typed lifecycle implementation — called by bsk_shim.rs
// ---------------------------------------------------------------------------

impl BskModule for mrpRustControllerConfig {
    // `feedforwardTorqueInMsg` is `Option<..>` here, so bsk-build treats it
    // as optional: no BasiliskError when it's left unconnected, and `update`
    // receives `None` instead of raising. See the Basilisk documentation's
    // "Writing a Rust Plugin" page (Messaging section).
    type Inputs = (AttGuidMsg, Option<CmdTorqueBodyMsg>);
    type Outputs = (CmdTorqueBodyMsg,);

    // Sanity-checks gains the same way a hand-written C module would with
    // `_bskLog(configData->bskLogger, BSK_WARNING, info)` — see
    // `BskLoggerExt` (bsk-messages) and the "Logging" section of the
    // Basilisk documentation's "Writing a Rust Plugin" page. A misconfigured
    // gain isn't fatal (unlike an unconnected required input, which
    // `bsk-build` already raises `BasiliskError` for automatically), so
    // `warning` — not `bsk_error` — is the appropriate level here.
    fn reset(&mut self, _current_sim_nanos: u64) -> Self::Outputs {
        if self.K <= 0.0 || self.P <= 0.0 {
            self.bskLogger.warning(&format!(
                "mrpRustController: non-positive gain (K={}, P={}) will not stabilize the spacecraft",
                self.K, self.P,
            ));
        }
        (CmdTorqueBodyMsg::default(),)
    }

    fn update(&mut self, inputs: Self::Inputs, _current_sim_nanos: u64) -> Self::Outputs {
        let (att_guid_in_msg, feedforward_torque_in_msg) = inputs;
        let k = self.K; // [Nm]
        let p = self.P; // [Nm/(rad/s)]
        let s = att_guid_in_msg.sigma_BR; // [-]     MRP attitude error
        let w = att_guid_in_msg.omega_BR_B; // [rad/s] body-rate error
        let l_ff = feedforward_torque_in_msg
            .map(|m| m.torqueRequestBody)
            .unwrap_or([0.0, 0.0, 0.0]); // [Nm] zero when unconnected

        (CmdTorqueBodyMsg {
            torqueRequestBody: [
                -k * s[0] - p * w[0] - l_ff[0],
                -k * s[1] - p * w[1] - l_ff[1],
                -k * s[2] - p * w[2] - l_ff[2],
            ],
        },)
    }
}

// ---------------------------------------------------------------------------
// Unit tests — run with `cargo test` (no Basilisk headers required)
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn make_cfg(k: f64, p: f64) -> mrpRustControllerConfig {
        mrpRustControllerConfig {
            runtime: BskModuleRuntime::for_testing(),
            K: k, // [Nm]
            P: p, // [Nm/(rad/s)]
            attGuidInMsg: Default::default(),
            feedforwardTorqueInMsg: Default::default(),
            cmdTorqueOutMsg: Default::default(),
            bskLogger: core::ptr::null_mut(),
        }
    }

    fn att(sigma: [f64; 3], omega: [f64; 3]) -> AttGuidMsg {
        AttGuidMsg {
            sigma_BR: sigma,
            omega_BR_B: omega,
            ..Default::default()
        }
    }

    fn run_update(
        config: &mut mrpRustControllerConfig,
        input: AttGuidMsg,
    ) -> CmdTorqueBodyMsg {
        let (output,) = config.update((input, None), 0);
        output
    }

    #[test]
    fn zero_error_gives_zero_torque() {
        let mut cfg = make_cfg(10.0, 30.0);
        let tau = run_update(&mut cfg, att([0.0; 3], [0.0; 3]));
        assert_eq!(tau.torqueRequestBody, [0.0, 0.0, 0.0]);
    }

    #[test]
    fn proportional_term_only() {
        let mut cfg = make_cfg(2.0, 0.0); // P = 0 isolates K
        let tau = run_update(&mut cfg, att([1.0, 0.0, 0.0], [0.0; 3]));
        assert!((tau.torqueRequestBody[0] - (-2.0)).abs() < 1e-12);
        assert_eq!(tau.torqueRequestBody[1], 0.0);
        assert_eq!(tau.torqueRequestBody[2], 0.0);
    }

    #[test]
    fn derivative_term_only() {
        let mut cfg = make_cfg(0.0, 5.0); // K = 0 isolates P
        let tau = run_update(&mut cfg, att([0.0; 3], [0.0, 1.0, 0.0]));
        assert_eq!(tau.torqueRequestBody[0], 0.0);
        assert!((tau.torqueRequestBody[1] - (-5.0)).abs() < 1e-12);
        assert_eq!(tau.torqueRequestBody[2], 0.0);
    }

    #[test]
    fn pd_combined_all_axes() {
        let k = 10.0_f64; // [Nm]
        let p = 30.0_f64; // [Nm/(rad/s)]
        let s = [0.1_f64, -0.05, 0.2]; // [-]
        let w = [0.01_f64, 0.0, -0.01]; // [rad/s]
        let mut cfg = make_cfg(k, p);
        let tau = run_update(&mut cfg, att(s, w));
        for i in 0..3 {
            let expected = -k * s[i] - p * w[i];
            assert!(
                (tau.torqueRequestBody[i] - expected).abs() < 1e-12,
                "axis {i}: got {}, expected {expected}",
                tau.torqueRequestBody[i]
            );
        }
    }

    /// `feedforwardTorqueInMsg` is `Option<..>` in `type Inputs`; passing
    /// `None` (the unconnected case) must not perturb the PD law.
    #[test]
    fn unconnected_feedforward_torque_adds_nothing() {
        let mut cfg = make_cfg(10.0, 30.0);
        let (output,) = cfg.update((att([1.0, 0.0, 0.0], [0.0; 3]), None), 0);
        assert_eq!(output.torqueRequestBody, [-10.0, 0.0, 0.0]);
    }

    /// A connected `feedforwardTorqueInMsg` (`Some(..)`) is subtracted
    /// directly from the PD torque.
    #[test]
    fn connected_feedforward_torque_is_subtracted() {
        let mut cfg = make_cfg(10.0, 30.0);
        let feedforward = CmdTorqueBodyMsg {
            torqueRequestBody: [0.25, -0.25, 0.1], // [Nm]
        };
        let (output,) = cfg.update((att([1.0, 0.0, 0.0], [0.0; 3]), Some(feedforward)), 0);
        assert!((output.torqueRequestBody[0] - (-10.25)).abs() < 1e-12);
        assert!((output.torqueRequestBody[1] - 0.25).abs() < 1e-12);
        assert!((output.torqueRequestBody[2] - (-0.1)).abs() < 1e-12);
    }
}
