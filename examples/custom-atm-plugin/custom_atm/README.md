# custom_atm

This directory defines the Python package that gets installed into the wheel.

It contains the `__init__.py` that registers Basilisk's `cSysModel` and imports
the compiled SWIG extension. At build time, scikit-build-core places the
generated `.so` / `.pyd` binaries and message bindings here.
