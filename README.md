# Basilisk SDK (`bsk-sdk`)

A self-contained Python wheel that gives external projects everything they need
to build [Basilisk](https://github.com/AVSLab/basilisk) compatible SWIG plugins
without vendoring the full simulation codebase.

## Quick start

```bash
pip install bsk-sdk
```

Then in your plugin's `CMakeLists.txt`:

```cmake
find_package(bsk-sdk CONFIG REQUIRED)

bsk_add_swig_module(
  TARGET myPlugin
  INTERFACE swig/myPlugin.i
  SOURCES myPlugin.cpp
  LINK_LIBS bsk::plugin
)
```

See [`examples/custom-atm-plugin/`](examples/custom-atm-plugin/) for a
complete working example.

## Syncing from Basilisk

The SDK vendors a curated subset of Basilisk headers and sources. These are
synced from a pinned Basilisk commit via a Git submodule.

```bash
git submodule update --init --recursive
python3 tools/sync_all.py
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

## Versioning

The `bsk-sdk` package version tracks the Basilisk version it was synced from
(e.g. `bsk-sdk==2.9.1` contains headers from Basilisk `v2.9.1`).

At CMake configure time, the SDK checks that the installed Basilisk version
matches and errors out on a mismatch. This prevents silent ABI
incompatibilities where plugins are compiled against headers from one Basilisk
version but linked against a different runtime.
