# numbaAtmosphere

This directory contains a pure-Python Basilisk module that is copied into the
`custom_atm` wheel package by `bsk_add_python_module()`. Its
`NumbaAtmosphere.UpdateStateImpl` method is JIT-compiled and called directly by
the Basilisk scheduler.

Read the [Basilisk Numba module guide](https://avslab.github.io/basilisk/Learn/makingModules/numbaModules.html)
before adding more complex numerical logic. In particular:

- Define every message attribute and persistent `memory` field before `Reset`.
- Name `UpdateStateImpl` parameters after their attributes. For example,
  `statusInMsgPayload` and `statusInMsgIsLinked` map to `self.statusInMsg`.
- Use an `InMsgIsLinked` parameter when a reader is optional.
- Do not override `UpdateState`. The scheduler calls the compiled function.
- If overriding `Reset`, call `super().Reset(CurrentSimNanos)`.

The first `Reset` validates the parameter-to-attribute mapping and message
links, then compiles the function in Numba's nopython mode. Basilisk caches the
compiled function for later modules and subsequent initialization.

This example reads and writes both message categories that SDK extensions use:

- Built-in `AtmoPropsMsg` objects from `Basilisk.architecture.messaging`.
- Extension-generated `CustomAtmStatusMsg` objects from `custom_atm.messaging`.

Import `custom_atm.messaging` before this module. Its generated `__init__.py`
registers `CustomAtmStatusMsgPayload.__dtype__` for `NumbaModel` and rejects
ambiguous payload-name collisions.
