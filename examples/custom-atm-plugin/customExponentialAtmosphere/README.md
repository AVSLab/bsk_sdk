# customExponentialAtmosphere

This directory follows the standard Basilisk module folder structure:

```
customExponentialAtmosphere/
  customExponentialAtmosphere.h      # Module header
  customExponentialAtmosphere.cpp    # Module implementation
  customExponentialAtmosphere.i      # SWIG interface file
  _UnitTest/                         # Unit and integration tests
    test_customExponentialAtmosphere.py
```

The module implements a simple exponential atmosphere model that extends
Basilisk's `AtmosphereBase`. It demonstrates how to:

- Subclass a Basilisk base class from an out-of-tree plugin
- Define and wire custom input messages
- Use `bsk_add_swig_module()` for SWIG wrapping
- Use `bsk_generate_messages()` for message payload bindings
