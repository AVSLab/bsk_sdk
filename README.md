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

If your extension needs additional link targets, pass them via `LINK_LIBS` and
they will be appended after the SDK defaults.

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

## Syncing from Basilisk

The SDK vendors a curated subset of Basilisk headers and sources. By default,
these are synced from the `external/basilisk` Git submodule. For a fresh clone,
initialize the submodule once before running the default sync:

```bash
# Only needed once in a fresh clone:
git submodule update --init --recursive

python3 tools/sync_all.py
pip install -e .
```

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

```bash
cd external/basilisk
git fetch && git checkout <tag-or-commit>
cd ../..
python3 tools/sync_all.py
```

Or sync from an existing Basilisk checkout without moving the submodule:

```bash
git -C ~/Repos/basilisk fetch --tags
git -C ~/Repos/basilisk checkout <tag-or-commit>
python3 tools/sync_all.py --basilisk-root ~/Repos/basilisk
```

## Versioning

The `bsk-sdk` package version tracks the Basilisk version it was synced from
(e.g. `bsk-sdk==2.9.1` contains headers from Basilisk `v2.9.1`).

At CMake configure time, the SDK checks that the installed Basilisk version
matches and errors out on a mismatch. This prevents silent ABI
incompatibilities where extensions are compiled against headers from one Basilisk
version but linked against a different runtime.
