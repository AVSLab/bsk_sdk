# custom-atm-extension

Example Basilisk extension built entirely out-of-tree using `bsk-sdk`.

This extension implements a simple exponential atmosphere model
(`CustomExponentialAtmosphere`) that extends Basilisk's `AtmosphereBase`.

## Directory structure

The layout follows the standard Basilisk module conventions:

```
custom-atm-extension/
  customExponentialAtmosphere/     # Module source, header, SWIG interface
    _UnitTest/                     # Tests (pytest)
  messages/                        # Extension-defined message payload headers
  planetStateProbe/                # Small C module using built-in BSK messages
  custom_atm/                      # Python package (wheel output)
  CMakeLists.txt                   # Build configuration
  pyproject.toml                   # Python packaging metadata
```

## Building

```bash
pip install bsk-sdk "bsk[all]"
pip install build scikit-build-core
python -m build --wheel --no-isolation
```

## Testing

```bash
pip install dist/*.whl pytest
pytest customExponentialAtmosphere/_UnitTest/ -v
```

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

## Built-in C message interfaces

C modules can include built-in Basilisk C message wrappers directly, using the
same include path as in Basilisk itself:

```c
#include "cMsgCInterface/SpicePlanetStateMsg_C.h"
```

The SDK ships and compiles these built-in definitions automatically through
`bsk_add_swig_module()`, so the extension `CMakeLists.txt` only lists the module's
own C source.
