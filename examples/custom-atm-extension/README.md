# custom-atm-extension

Example Basilisk extension built entirely out-of-tree using `bsk-sdk`.

This extension implements a simple exponential atmosphere model
(`CustomExponentialAtmosphere`) that extends Basilisk's `AtmosphereBase`, plus
a pure-Python `NumbaAtmosphere` module whose update is JIT-compiled by numba.

## Directory structure

The layout follows the standard Basilisk module conventions:

```
custom-atm-extension/
  customExponentialAtmosphere/     # Module source, header, SWIG interface
    _UnitTest/                     # Tests (pytest)
  numbaAtmosphere/                 # Pure-Python Numba module and test
  messages/                        # Extension-defined message payload headers
  planetStateProbe/                # Small C module using built-in BSK messages
  custom_atm/                      # Python package (wheel output)
  CMakeLists.txt                   # Build configuration
  pyproject.toml                   # Python packaging metadata
```

## Building

Run the following commands from the root of the `bsk-sdk` repository. Running
the import checks from this example directory would put the unbuilt
`custom_atm` source package ahead of the installed wheel on Python's import
path.

```bash
python -m pip install bsk-sdk build scikit-build-core
# For a published SDK/BSK release:
python -c "import bsk_sdk, subprocess, sys; subprocess.run([sys.executable, '-m', 'pip', 'install', f'bsk[all]=={bsk_sdk.bsk_version()}'], check=True)"
# For an alpha or beta SDK whose BSK wheel is on the nightly index instead:
python -m pip install --pre --index-url https://avslab.github.io/basilisk/nightly/ --extra-index-url https://pypi.org/simple/ "bsk[all]"
python -c "import Basilisk, bsk_sdk; print('Basilisk:', Basilisk.__version__); print('SDK synced from:', bsk_sdk.bsk_version())"
python -m build --wheel --no-isolation -o extension-dist examples/custom-atm-extension
```

## Testing

```bash
python -m pip install extension-dist/*.whl pytest
python -c "import Basilisk, numba, custom_atm; from custom_atm import numbaAtmosphere"
python -m pytest examples -v
```

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

## Built-in C message interfaces

C modules can include built-in Basilisk C message wrappers directly, using the
same include path as in Basilisk itself:

```c
#include "cMsgCInterface/SpicePlanetStateMsg_C.h"
```

The SDK ships and compiles these built-in definitions automatically through
`bsk_add_swig_module()`, so the extension `CMakeLists.txt` only lists the module's
own C source.
