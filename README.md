# Basilisk SDK (`bsk-sdk`)

A self-contained Python wheel that gives external projects everything they need
to build [Basilisk](https://github.com/AVSLab/basilisk) compatible SWIG extensions
without vendoring the full simulation codebase.

## Quick start

```bash
pip install bsk-sdk
```

Then in your extension's `CMakeLists.txt`:

```cmake
find_package(bsk-sdk CONFIG REQUIRED)

bsk_add_swig_module(
  TARGET myExtension
  INTERFACE swig/myExtension.i
  SOURCES myExtension.cpp
)
```

`bsk_add_swig_module` automatically compiles the vendored Basilisk SDK sources
(arch_min, arch_utilities, runtime_min, and built-in C message interfaces)
directly into your extension, so no separate link targets are needed. Basilisk
utility headers are available at their standard paths, for example:

```cpp
#include "architecture/utilities/orbitalMotion.h"
```

C modules can include built-in message C interfaces at the same paths used by
Basilisk modules:

```c
#include "cMsgCInterface/SpicePlanetStateMsg_C.h"
```

If a C or C++ extension built with `bsk_add_swig_module()` needs additional
link targets, pass them through its `LINK_LIBS` argument. They are appended
after the SDK's default libraries.

## Runtime compatibility guard

Extension wheels contain native code compiled for one exact Basilisk release.
Record that release in the wheel metadata and generate a package-level guard:

```toml
[build-system]
requires = ["bsk-sdk==2.X.Y", "bsk==2.X.Y"]

[project]
dependencies = ["bsk==2.X.Y"]
```

```cmake
bsk_add_extension_compatibility_guard(
  EXTENSION_NAME "my_extension"
  OUTPUT_DIR "${SKBUILD_PLATLIB_DIR}/my_extension"
)
```

Import the generated guard before any compiled module in the package's
`__init__.py`:

```python
from ._bsk_compatibility import check_basilisk_compatibility as _check_basilisk

_check_basilisk()
del _check_basilisk
```

The dependency metadata helps pip preserve a compatible environment. The guard
also catches a later forced upgrade or other environment change before native
code is loaded, and reports how to install the expected BSK version.

## Rust modules

An extension can package native Rust Basilisk modules alongside its C, C++,
Numba, and Python modules. Rust is needed only when the extension calls the
Rust CMake helper; C/C++-only extension projects and users installing a
prebuilt extension wheel see no new tool requirement.

Put the extension's Rust packages in one Cargo workspace and mark each module
with `[package.metadata.basilisk] module = true`. After generating any custom
messages, add one call to the extension's `CMakeLists.txt`:

```cmake
bsk_add_rust_workspace(
  MANIFEST "${CMAKE_CURRENT_SOURCE_DIR}/Cargo.toml"
  OUTPUT_DIR "${EXTENSION_PKG_DIR}"
)
```

Rust modules can use the built-in C messages shipped by `bsk-sdk`. To use an
extension-owned payload, pass `GENERATE_C_INTERFACE` to
`bsk_generate_messages()` before calling `bsk_add_rust_workspace()`. Cargo and
the Rust compiler are discovered only when the workspace helper is invoked;
the SDK supplies the pinned Corrosion integration and message-generation
paths automatically.

The installed Basilisk wheel does not need in-tree Rust modules enabled. Query
the compatible compiler and support-crate versions directly from the SDK:

```bash
python -c "import bsk_sdk; print('Rust:', bsk_sdk.rust_minimum_version()); print('bsk-* crates:', bsk_sdk.rust_support_crate_version())"
```

Released extensions obtain the support crates from the matching Basilisk Git
tag. Cargo caches that checkout outside the extension source tree. During SDK
development, `tools/sync_all.py` instead writes local path dependencies that
use the exact Basilisk checkout selected with `--basilisk-root`. The default
`external/basilisk` checkout is recorded with portable relative paths.

The [`rustAtmosphere`](examples/custom-atm-extension/rustAtmosphere/) example
reads and writes both a built-in Basilisk message and an extension-owned
message. The [Basilisk Rust module guide](https://avslab.github.io/basilisk/Learn/makingModules/rustModules.html)
covers the module API, lifecycle, ports, configuration, and testing patterns.

See [`examples/custom-atm-extension/`](examples/custom-atm-extension/) for a
complete working example.

## Pure-Python and Numba modules

Basilisk 2.11 introduced `NumbaModel` for Python modules whose update method is
JIT-compiled and called directly by the C++ scheduler. Extension projects can
keep these modules in the same conventional source layout as compiled modules
and copy them into the wheel package with `bsk_add_python_module`:

```cmake
bsk_add_python_module(
  SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/numbaAtmosphere/numbaAtmosphere.py"
  OUTPUT_DIR "${SKBUILD_PLATLIB_DIR}/my_extension"
)
```

The module subclasses `Basilisk.architecture.numbaModel.NumbaModel`; it does
not need a SWIG interface or native build target. Add both `bsk` and `numba` to
the extension's runtime dependencies rather than adding Numba to `bsk-sdk`,
since extensions that only build C or C++ modules do not need it.

When `bsk_generate_messages()` creates extension-owned message bindings, their
payload dtypes are registered for `NumbaModel` automatically. Import the
generated messaging package before the Numba module; a duplicate payload name
raises an import error instead of replacing an existing Basilisk dtype.

See the [Basilisk Numba module guide](https://avslab.github.io/basilisk/Learn/makingModules/numbaModules.html)
for the `UpdateStateImpl` naming rules and nopython-mode constraints. The
[`scenarioNumbaAtmosphereExtension.py`](examples/scenarioNumbaAtmosphereExtension.py)
is an executable example using the installed extension wheel.

### Message lifetime support

Starting with Basilisk 2.12, messages generated through
`bsk_generate_messages()` participate in Basilisk's source-retention behavior.
An object-based reader subscription or message recorder keeps its stand-alone
source alive until the subscription or recorder is released. This includes
extension-defined C++ readers, `Message.recorder()`, and direct
`Recorder(Message)` construction.

The SDK also synchronizes Basilisk's owner-aware C-message wrapper support, so
wrapped C modules retain the config or module object that owns an embedded
`Msg_C` source rather than a transient SWIG proxy. Raw-address subscriptions
remain caller-owned and do not create a keep-alive reference.

## Building and testing

In a fresh clone, generate the ignored SDK artifacts before disabling automatic
sync. Then build and install the SDK wheel and run every SDK test under `tests`:

```bash
python -m pip install build pytest
python3 tools/sync_all.py
BSK_SDK_AUTO_SYNC=0 python -m build --wheel -o dist
python -m pip install --force-reinstall dist/*.whl
python -m pytest tests -v
```

To test the examples, first install the Basilisk version reported by
`bsk_sdk.bsk_version()`. Then build and install the example extension wheel and
run every test collected under `examples`. The bundled example contains a Rust
module, so install Rust 1.89 or newer with [rustup](https://rustup.rs/) first:

```bash
python -m pip install build scikit-build-core pytest
# For a published SDK/BSK release:
python -c "import bsk_sdk, subprocess, sys; subprocess.run([sys.executable, '-m', 'pip', 'install', f'bsk[all]=={bsk_sdk.bsk_version()}'], check=True)"
# For an alpha or beta SDK whose BSK wheel is on the nightly index instead:
python -m pip install --pre --index-url https://avslab.github.io/basilisk/nightly/ --extra-index-url https://pypi.org/simple/ "bsk[all]"
python -c "import Basilisk, bsk_sdk; print('Basilisk:', Basilisk.__version__); print('SDK synced from:', bsk_sdk.bsk_version())"
python -m build --wheel --no-isolation -o extension-dist \
  -Cbuild-dir=extension-build examples/custom-atm-extension
python -m pip install extension-dist/*.whl
python -c "import Basilisk, numba, custom_atm; from custom_atm import numbaAtmosphere, rustAtmosphere"
python -m pytest examples -v
BSK_CMSG_DIRS="$(python -c 'import bsk_sdk; print(bsk_sdk.c_msg_interface_dir())'):$(pwd)/extension-build/autoSource/cMsgCInterface" \
BSK_SRC_ROOT="$(python -c 'import bsk_sdk; print(bsk_sdk.include_dir())')/Basilisk" \
  cargo test --manifest-path examples/custom-atm-extension/Cargo.toml --workspace --locked
```

The Python tests validate the installed wheel and Basilisk scheduler
integration; `cargo test` runs the module's Rust-native tests. On Linux, set
`LIBCLANG_PATH` before running Cargo:

```bash
export LIBCLANG_PATH="$(python -c 'import bsk_sdk; print(bsk_sdk.rust_libclang_dir())')"
```

On Windows, set all three environment variables in PowerShell and use `;`
rather than `:` between the two paths in `BSK_CMSG_DIRS`. On macOS, leave
`LIBCLANG_PATH` unset so the binding generator uses the libclang supplied with
Xcode and compatible with the active SDK headers.

Rust extension wheels statically incorporate Rust dependencies. Generate and
commit their license report with the pinned generator and `cargo-about` policy
reported by `bsk_sdk.rust_license_generator()` and
`bsk_sdk.rust_license_config()`. The custom-atmosphere example demonstrates the
command and packages the resulting report with its Python module. The report
defaults to an ISC project-license statement; pass `--project-license` when
your extension uses a different license. Because the installed SDK does not
own an extension workspace or output package, its generator requires explicit
`--manifest-path` and `--output` arguments.

The explicit `tests` and `examples` paths avoid collecting tests from the
`external/basilisk` submodule while automatically including new SDK and
example tests added under those directories.

## Syncing from Basilisk

The SDK vendors a curated subset of Basilisk headers and sources, including
the CMake files that define its Rust minimum version, support-crate version,
and pinned Corrosion revision. By default, these are synced from the
`external/basilisk` Git submodule. The normal sync command initializes that
submodule when necessary and checks out the exact Basilisk commit recorded by
the SDK repository:

```bash
python3 tools/sync_all.py
pip install -e .
```

The command reports the selected Basilisk directory and its full Git commit ID
before copying files. This makes the source used for a sync visible in build
logs. If an automation job places a standalone Git clone at
`external/basilisk`, synchronization preserves that clone's selected branch or
tag instead of treating it as the SDK submodule.

If you already have a local Basilisk checkout, point the sync script at it
directly instead of moving the submodule checkout:

```bash
git -C ~/Repos/basilisk fetch --tags
git -C ~/Repos/basilisk checkout <tag-or-branch>
python3 tools/sync_all.py --basilisk-root ~/Repos/basilisk
pip install -e .
```

Or opt into auto-sync during build:

```bash
BSK_SDK_AUTO_SYNC=1 pip install -e .
```

### Updating to a newer Basilisk version

The SDK records one exact Basilisk commit for `external/basilisk`. Updating
that record is a maintainer operation. First choose the desired commit in a
Basilisk checkout. A *commit ID* (also called a commit hash or SHA) is the
40-character identifier printed by this command:

```bash
BSK_ROOT=~/Repos/basilisk
git -C "$BSK_ROOT" rev-parse HEAD
```

Here, `HEAD` means "the latest committed state currently checked out in this
particular repository." It does not include uncommitted file edits. A commit
message is descriptive text and should not be used in place of the commit ID.

To make `external/basilisk` use that same commit, fetch the Basilisk remote,
then copy the printed commit ID into the checkout command:

```bash
git -C external/basilisk fetch origin
git -C external/basilisk checkout <desired-exact-commit>
git add external/basilisk
python3 tools/sync_all.py
```

The `git add` command records the new submodule pointer in the SDK's next
commit; it does not copy the Basilisk repository into the SDK.

`HEAD` can also be resolved automatically from the checkout named by
`BSK_ROOT`, avoiding manual copying:

```bash
git -C external/basilisk fetch origin
git -C external/basilisk checkout "$(git -C "$BSK_ROOT" rev-parse HEAD)"
git add external/basilisk
python3 tools/sync_all.py
```

Once the pointer is committed, other developers need only run
`python3 tools/sync_all.py`; they do not choose the commit again. To test a
temporary, unrecorded checkout under `external/basilisk`, pass
`--no-sync-submodules` so synchronization does not restore the recorded
commit.

Or sync from an existing Basilisk checkout without moving the submodule:

```bash
git -C ~/Repos/basilisk fetch --tags
git -C ~/Repos/basilisk checkout <tag-or-commit>
python3 tools/sync_all.py --basilisk-root ~/Repos/basilisk
```

### Rust dependency selection

`tools/sync_all.py` reads the selected checkout's
`docs/source/bskVersion.txt` and updates the example automatically. It pins the
example's build-time `bsk-sdk` and `bsk` requirements and its runtime `bsk`
requirement to that version. It also selects the Rust support source:

- final and release-candidate versions use the matching immutable Basilisk
  Git tag, such as `v2.12.0`;
- development versions use direct paths to the checkout passed through
  `--basilisk-root`.

No manual `Cargo.toml` edit is required when changing SDK branches or preparing
a release. After selecting a different checkout, run the normal sync command:

```bash
python3 tools/sync_all.py --basilisk-root <path-to-basilisk>
```

For a numbered or release-candidate build, refresh and commit both the example
lockfile and its Rust third-party license report after synchronization. The
dependency source changes from local paths to a Git tag, which can change the
packages classified as external to the extension:

```bash
cargo generate-lockfile \
  --manifest-path examples/custom-atm-extension/Cargo.toml
CARGO_ABOUT_VERSION="$(python -c 'import json; print(json.load(open("src/bsk_sdk/rust/support-versions.json"))["BSK_CARGO_ABOUT_VERSION"])')"
cargo install cargo-about \
  --version "=${CARGO_ABOUT_VERSION}" --locked --features cli
python src/bsk_sdk/rust/licenses/generate_rust_licenses.py \
  --manifest-path examples/custom-atm-extension/Cargo.toml \
  --config src/bsk_sdk/rust/licenses/about.toml \
  --output examples/custom-atm-extension/custom_atm/RUST-THIRD-PARTY.txt \
  --project-name custom-atm-extension --require-tool
```

The release workflow rejects a stale manifest, lockfile, or license report,
then builds and tests the example extension against the tagged dependency
graph before publishing. Extension users pay this Git download only while
building their wheel; Cargo stores it in its global cache, and the installed
extension wheel does not require Rust or the Basilisk source.

## Versioning

The `bsk-sdk` package version tracks the Basilisk version it was synced from
(e.g. `bsk-sdk==2.9.1` contains headers from Basilisk `v2.9.1`).

At CMake configure time, the SDK checks that the installed Basilisk version
matches and errors out on a mismatch. This prevents silent ABI
incompatibilities where extensions are compiled against headers from one Basilisk
version but linked against a different runtime. Extension wheels that use
`bsk_add_extension_compatibility_guard()` repeat the exact-version and extension
ABI check on every package import, before loading compiled modules.
