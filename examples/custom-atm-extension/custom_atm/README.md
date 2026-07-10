# custom_atm

This directory defines the Python package that gets installed into the wheel.

It contains the `__init__.py` that registers Basilisk's `cSysModel`, imports
the generated custom message bindings, and then imports the compiled SWIG
extension. At build time, scikit-build-core places the generated `.so` / `.pyd`
binaries and message bindings here.

The generated `messaging` package must be imported before module wrappers that
expose custom message fields. That import registers the SWIG proxy classes for
the extension's `Message<T>` and `Recorder<T>` specializations, which makes calls
such as `module.customOutMsg.recorder()` work without an extra user import.
