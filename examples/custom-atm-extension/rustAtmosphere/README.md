# rustAtmosphere

`rustAtmosphere` is a native Rust Basilisk module compiled into the example
extension wheel. It reads and writes both a built-in Basilisk C message and the
extension-owned `CustomAtmStatusMsg`, providing an end-to-end test of SDK Rust
workspace discovery, custom C-message generation, SWIG wrapping, and wheel
packaging.

## Configuration and messages

`densityScale` is a non-negative, dimensionless multiplier. Assignments are
validated immediately by the generated Python setter.

The module uses these ports:

| Port | Direction | Message | Purpose |
| --- | --- | --- | --- |
| `atmoInMsg` | Input, required | `AtmoPropsMsg` | Built-in Basilisk atmosphere data |
| `statusInMsg` | Input, optional | `CustomAtmStatusMsg` | Extension-owned density and scale height |
| `atmoOutMsg` | Output | `AtmoPropsMsg` | Scaled built-in atmosphere data |
| `statusOutMsg` | Output | `CustomAtmStatusMsg` | Scaled extension status data |

When a valid custom status input is connected, its density and scale height
are used. Otherwise, the module scales the built-in atmosphere density. The
private update counter demonstrates Rust state that is neither copied through
the C boundary nor exposed to Python.

The Python tests execute the installed module through Basilisk's scheduler and
verify both message families, the optional-input fallback, timestamps, module
IDs, write flags, and configuration validation. The Rust-native test checks the
validator without constructing a Python simulation.

The module is registered in the extension's root `Cargo.toml`; the extension
calls `bsk_add_rust_workspace()` once from `CMakeLists.txt`. See Basilisk's
[“Making Rust Modules” guide](https://avslab.github.io/basilisk/Learn/makingModules/rustModules.html)
for the complete module API and coding patterns. The root workspace owns the
single committed `Cargo.lock`; do not add a second lockfile to this directory.
