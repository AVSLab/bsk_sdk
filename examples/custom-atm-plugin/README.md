# custom-atm-plugin

Example Basilisk plugin built entirely out-of-tree using `bsk-sdk`.

This plugin implements a simple exponential atmosphere model
(`CustomExponentialAtmosphere`) that extends Basilisk's `AtmosphereBase`.

## Directory structure

The layout follows the standard Basilisk module conventions:

```
custom-atm-plugin/
  customExponentialAtmosphere/     # Module source, header, SWIG interface
    _UnitTest/                     # Tests (pytest)
  messages/                        # Plugin-defined message payload headers
  custom_atm/                      # Python package (wheel output)
  CMakeLists.txt                   # Build configuration
  pyproject.toml                   # Python packaging metadata
```

## Building

```bash
pip install bsk-sdk bsk
pip install build scikit-build-core
python -m build --wheel --no-isolation
```

## Testing

```bash
pip install dist/*.whl pytest
pytest customExponentialAtmosphere/_UnitTest/ -v
```
