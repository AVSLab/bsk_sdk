# Basilisk SDK

This package publishes the Basilisk plugin SDK so that external projects can
build Basilisk-compatible SWIG based plugins without vendoring the full simulation
codebase. It ships curated Basilisk headers, SWIG interface files and typemaps,
message auto-generation tools, and CMake helper functions for building SWIG
modules out-of-tree.

## Syncing from Basilisk (versioned)

Recommended approach: add Basilisk as a Git submodule so the SDK can sync from a
pinned Basilisk commit.

```bash
git submodule add https://github.com/AVSLab/basilisk.git external/basilisk
git submodule update --init --recursive
```

Commit policy:

- Commit `.gitmodules` and the `external/basilisk` gitlink (submodule pointer).
- Do **not** vendor/copy Basilisk repo contents directly into this SDK repo.

Then run:

```bash
python3 tools/sync_all.py --sync-submodules
pip install -e .
```

By default, builds are side-effect free and require sync artifacts to already be
present.

If you want convenience auto-sync during build, opt in:

```bash
BSK_SDK_AUTO_SYNC=1 pip install -e .
```

Build/sync behavior can be controlled with environment variables:

- `BSK_SDK_AUTO_SYNC=1` enables auto-sync during build.
- `BSK_SDK_SYNC_SUBMODULES=0` skips submodule update during auto-sync.
- `BSK_BASILISK_ROOT=/path/to/basilisk` overrides source location.

Path resolution order used by sync scripts:

1. `--basilisk-root <path>`
2. `BSK_BASILISK_ROOT=<path>`
3. `external/basilisk` (submodule default)
4. `../basilisk` (legacy sibling fallback)

Examples:

```bash
python3 tools/sync_all.py --basilisk-root ~/src/basilisk
BSK_BASILISK_ROOT=~/src/basilisk python3 tools/sync_all.py
```

To update to a newer Basilisk version:

```bash
cd external/basilisk
git fetch
git checkout <basilisk-tag-or-commit>
cd ../..
python3 tools/sync_all.py
```
