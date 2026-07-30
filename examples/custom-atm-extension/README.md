# custom-atm-extension

Example Basilisk extension built entirely out-of-tree using `bsk-sdk`.

This extension implements a simple exponential atmosphere model
(`CustomExponentialAtmosphere`) that extends Basilisk's `AtmosphereBase`, plus
a pure-Python `NumbaAtmosphere` module whose update is JIT-compiled by numba
and a native `rustAtmosphere` module built through the SDK's Cargo integration.

## Directory structure

The layout follows the standard Basilisk module conventions:

```
custom-atm-extension/
  customExponentialAtmosphere/     # Module source, header, SWIG interface
    _UnitTest/                     # Tests (pytest)
  rustAtmosphere/                  # Native Rust module and tests
  numbaAtmosphere/                 # Pure-Python Numba module and test
  messages/                        # Extension-defined message payload headers
  planetStateProbe/                # Small C module using built-in BSK messages
  custom_atm/                      # Python package (wheel output)
    _bsk_compatibility.py          # Generated runtime version and ABI guard
  Cargo.toml                       # Shared Rust workspace
  Cargo.lock                       # Reviewed Rust dependency resolution
  CMakeLists.txt                   # Build configuration
  pyproject.toml                   # Python packaging metadata
```

## Building

Run the following commands from the root of the `bsk-sdk` repository. Running
the import checks from this example directory would put the unbuilt
`custom_atm` source package ahead of the installed wheel on Python's import
path.

```bash
python -m pip install build scikit-build-core
python -m build --wheel -o sdk-dist .
python -m pip install --force-reinstall sdk-dist/bsk_sdk-*.whl
rustc --version  # Rust 1.89 or newer; install with https://rustup.rs/
python -c "import bsk_sdk; print('Rust:', bsk_sdk.rust_minimum_version()); print('bsk-* crates:', bsk_sdk.rust_support_crate_version())"
# For a published SDK/BSK release:
python -c "import bsk_sdk, subprocess, sys; subprocess.run([sys.executable, '-m', 'pip', 'install', f'bsk[all]=={bsk_sdk.bsk_version()}'], check=True)"
# For an alpha or beta SDK whose BSK wheel is on the nightly index instead:
python -m pip install --pre --index-url https://avslab.github.io/basilisk/nightly/ --extra-index-url https://pypi.org/simple/ "bsk[all]"
python -c "import Basilisk, bsk_sdk; print('Basilisk:', Basilisk.__version__); print('SDK synced from:', bsk_sdk.bsk_version())"
python -m build --wheel --no-isolation -o extension-dist \
  -Cbuild-dir=extension-build examples/custom-atm-extension
```

These commands deliberately install the SDK wheel built from the current
checkout. A standalone extension targeting a published release can instead
install the matching `bsk-sdk==2.X.Y` package.

## Testing

```bash
python -m pip install extension-dist/*.whl pytest
python -c "import Basilisk, numba, custom_atm; from custom_atm import numbaAtmosphere, rustAtmosphere"
python -m pytest examples -v
BSK_CMSG_DIRS="$(python -c 'import bsk_sdk; print(bsk_sdk.c_msg_interface_dir())'):$(pwd)/extension-build/autoSource/cMsgCInterface" \
BSK_SRC_ROOT="$(python -c 'import bsk_sdk; print(bsk_sdk.include_dir())')/Basilisk" \
  cargo test --manifest-path examples/custom-atm-extension/Cargo.toml --workspace --locked
```

The final command runs Rust-native tests. On Linux, first run:

```bash
export LIBCLANG_PATH="$(python -c 'import bsk_sdk; print(bsk_sdk.rust_libclang_dir())')"
```

On Windows, set all three environment variables in PowerShell and separate
`BSK_CMSG_DIRS` entries with `;`. On macOS, leave `LIBCLANG_PATH` unset so the
binding generator uses Xcode's matching libclang.

## BSK compatibility

The example pins `bsk-sdk` and `bsk` during the build and records the same exact
`bsk` requirement in the completed wheel. Within this repository,
`tools/sync_all.py` updates those requirements from the selected Basilisk
checkout; extension developers choose the release their own wheel targets.

`bsk_add_extension_compatibility_guard()` also generates
`custom_atm/_bsk_compatibility.py`. The package runs this guard before importing
its C, C++, or Rust wrappers. If BSK is later replaced with another version, the
package raises a descriptive `ImportError` instead of loading incompatible
native code.

## Rust module

`rustAtmosphere/rustAtmosphere.rs` follows the normal Basilisk Rust module API
described in the [Making Rust Modules guide](https://avslab.github.io/basilisk/Learn/makingModules/rustModules.html).
The extension-specific pieces are:

- the root `Cargo.toml` is a workspace containing every Rust module package;
- each module sets `[package.metadata.basilisk] module = true`;
- the workspace commits one `Cargo.lock` and uses the Rust panic policy
  required by Basilisk; and
- `CMakeLists.txt` calls `bsk_add_rust_workspace()` once, after custom message
  generation.

Numbered SDK releases get `bsk-build` and `bsk-messages` from the matching
immutable Basilisk Git tag. In the BSK-SDK repository, `tools/sync_all.py`
selects direct path dependencies so branch testing compiles against the exact
`external/basilisk` or `--basilisk-root` checkout without a manual edit.
Cargo stores downloaded Git dependencies in its global cache rather than in
the extension source directory.

The example module reads and writes `AtmoPropsMsg`, a built-in Basilisk C
message, and `CustomAtmStatusMsg`, which belongs to this extension. Its private
update counter also demonstrates state that remains entirely inside Rust and
does not become a Python-visible configuration field.

Adding another Rust module requires adding its directory to the workspace
members and marking its package as a Basilisk module. CMake discovers the
marked static-library target through Cargo metadata; no per-module CMake call
is needed. Update and commit `Cargo.lock` after changing the workspace or its
dependencies.

The installed Basilisk wheel does not need to contain in-tree Rust modules.
This extension compiles its Rust archive itself and obtains compatible built-in
C-message interfaces from `bsk-sdk`.

## Rust dependency licenses

Rust dependencies are statically incorporated into the native extension
module. The example packages `custom_atm/RUST-THIRD-PARTY.txt` alongside its ISC
license. Regenerate the report whenever `Cargo.lock` changes:

```bash
CARGO_ABOUT_VERSION="$(python -c 'import bsk_sdk; print(bsk_sdk.rust_license_tool_version())')"
cargo install cargo-about --version "=${CARGO_ABOUT_VERSION}" --locked --features cli
python -c "import bsk_sdk; print(bsk_sdk.rust_license_generator()); print(bsk_sdk.rust_license_config())"
python <generator-path> --manifest-path examples/custom-atm-extension/Cargo.toml \
  --config <config-path> \
  --output examples/custom-atm-extension/custom_atm/RUST-THIRD-PARTY.txt \
  --project-name custom-atm-extension --require-tool
```

Use `--check` instead of rewriting the file in CI.

## Numba module

`numbaAtmosphere/numbaAtmosphere.py` uses the source layout of a normal
Basilisk module, but it subclasses `NumbaModel` and therefore needs no SWIG
interface or C/C++ target. The extension copies it into `custom_atm` with:

```cmake
bsk_add_python_module(
  SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/numbaAtmosphere/numbaAtmosphere.py"
  OUTPUT_DIR "${EXTENSION_PKG_DIR}"
)
```

The `bsk` and `numba` runtime dependencies are declared in `pyproject.toml`.
`UpdateStateImpl` parameter names identify the corresponding message attributes,
so those attributes and all `memory` fields must be created before `Reset`.
The first `Reset` validates message links, JIT-compiles the update in nopython
mode, and may populate the Numba cache; do not override `UpdateState`.

See the [Basilisk Numba module guide](https://avslab.github.io/basilisk/Learn/makingModules/numbaModules.html)
for the complete API and supported operations. The module-specific
[`numbaAtmosphere/README.md`](numbaAtmosphere/README.md) walks through this
example. Once the wheel is installed, run the repository scenario from its root:

```bash
python examples/scenarioNumbaAtmosphereExtension.py
```

The scenario exchanges a built-in atmosphere message and an extension-generated
status message, then executes three JIT-compiled updates through Basilisk's
normal task scheduler.

## Custom message recorders

If an extension defines custom messages with `bsk_generate_messages()`, import the
generated message package from the extension's top-level `__init__.py` before
importing module wrappers:

```python
from . import messaging
from . import myModule
```

This mirrors Basilisk's own package initialization. It registers the custom
`Message<T>` and `Recorder<T>` SWIG proxy classes so users can call
`module.customOutMsg.recorder()` without explicitly importing the message type.
It also exposes generated payload dtypes to `NumbaModel`. Registration is
idempotent, and a duplicate payload name raises an import error instead of
silently replacing a Basilisk or another extension's payload class.

Pass `GENERATE_C_INTERFACE` when a custom message is used by a Rust or C
module. This produces the C ABI that `bsk-messages` binds for the Rust module;
the same generated payload remains available through the extension's Python
`messaging` package.

## Built-in C message interfaces

C modules can include built-in Basilisk C message wrappers directly, using the
same include path as in Basilisk itself:

```c
#include "cMsgCInterface/SpicePlanetStateMsg_C.h"
```

The SDK ships and compiles these built-in definitions automatically through
`bsk_add_swig_module()`, so the extension `CMakeLists.txt` only lists the module's
own C source.
