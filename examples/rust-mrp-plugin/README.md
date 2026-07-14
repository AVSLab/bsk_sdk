# rust-mrp-plugin

A Basilisk attitude controller implemented in Rust, demonstrating how to write
an out-of-tree BSK module using the `bsk-sdk`.  The Rust module replaces the
built-in C++ `mrpFeedback` module with a PD controller:

```
τ = −K σ_BR − P ω_BR
```

This example is intentionally minimal — a pattern demo, not a
feature-complete port of `mrpFeedback`. For the full feature set the Rust
module system supports (multiple/optional message ports, stateful modules,
build & packaging details, testing at every layer), see the Basilisk
documentation's
[Writing a Rust Plugin](https://avslab.github.io/basilisk/develop/Plugins/writingRust.html)
page.

## Directory layout

```
rust-mrp-plugin/
  mrpRustController/          Rust crate + Python package
    src/lib.rs                  config struct (#[repr(C)]) + pure-Rust algorithm
    build.rs                    3-line stub — delegates to bsk-build
    Cargo.toml
    __init__.py                 makes this directory a Python package
    _UnitTest/
      test_mrpRustController.py   unit tests (BSK simulation harness)
      test_scenarioAttitudeFeedbackRust.py
  scenarioAttitudeFeedbackRust.py   full attitude-control scenario
  CMakeLists.txt
  pyproject.toml
```

## Prerequisites

| Tool | Minimum | Install |
|------|---------|---------|
| Python | 3.9 | system or pyenv |
| Rust / Cargo | 1.75 | `curl https://sh.rustup.rs -sSf \| sh` |
| CMake | 3.26 | `apt install cmake` |
| Basilisk (local build) | — | see below |
| bsk-sdk | — | see below |

---

## Quick start

### 1 — Set up Python environment

```bash
cd $HOME/bsk_sdk
python3 -m venv .venv
source .venv/bin/activate
```

### 2 — Install Basilisk from source

```bash
python -m pip install -e $HOME/basilisk
```

### 3 — Install bsk-sdk

```bash
BSK_SDK_AUTO_SYNC=0 python -m pip install -e $HOME/bsk_sdk \
  build pytest scikit-build-core cmake ninja
```

The editable Basilisk installation uses the native modules already built in
`$HOME/basilisk/dist3`. Build them there first if they are absent.

### 4 — Generate Rust bindings (once, or after a Basilisk header sync)

```bash
cargo install bindgen-cli          # one-time
python3 $HOME/bsk_sdk/tools/gen_rust_messages.py \
    --bsk-include $HOME/bsk_sdk/src/bsk_sdk/include
python3 $HOME/bsk_sdk/tools/gen_rust_utilities.py \
    --bsk-include $HOME/bsk_sdk/src/bsk_sdk/include
```

The second command generates `bsk-utilities`: thin Rust wrappers around the
Basilisk C ABI utilities and constants.  It deliberately excludes C++/Eigen
interfaces.

---

## Running the Rust unit tests (no Basilisk required)

The controller algorithm (`update()`) is pure Rust.  Test it without any BSK 
headers or Python:

```bash
cd mrpRustController
cargo test
```

Expected output:

```
running 4 tests
test tests::zero_error_gives_zero_torque ... ok
test tests::proportional_term_only       ... ok
test tests::derivative_term_only         ... ok
test tests::pd_combined_all_axes         ... ok

test result: ok. 4 passed; 0 failed; 0 ignored
```

---

## Development workflow: build-tree package

Use direct CMake while iterating on Rust, C++, or CMake code. It writes all
generated artifacts to `_build/python/mrpRustController`; the source tree stays
unchanged.

```bash
cd $HOME/bsk_sdk/examples/rust-mrp-plugin
source $HOME/bsk_sdk/.venv/bin/activate

cmake -S . -B _build -DCMAKE_BUILD_TYPE=Release
cmake --build _build --parallel
```

CMake automatically:
1. Runs `cargo build --release` (which generates `mrpRustController.h` in the
   CMake build tree via bsk-build)
2. Runs SWIG to generate `_build/python/mrpRustController/mrpRustController.py`
3. Compiles `_build/python/mrpRustController/_mrpRustController.so`

---

## Running the Python tests

The CMake project registers its test suite with CTest and supplies the
build-tree package path automatically:

```bash
cd $HOME/bsk_sdk/examples/rust-mrp-plugin
source $HOME/bsk_sdk/.venv/bin/activate
ctest --test-dir _build --output-on-failure
```

---

## Installing during development

An editable install builds the extension in scikit-build-core's build tree and
makes the package importable from the active environment. It does not write
generated files into `mrpRustController/`.

```bash
cd $HOME/bsk_sdk/examples/rust-mrp-plugin
source $HOME/bsk_sdk/.venv/bin/activate
python -m pip install -e . --no-build-isolation
python -c "from mrpRustController import mrpRustController; print(mrpRustController.__file__)"
```

Re-run the editable-install command after Rust, C++, or CMake changes to
rebuild the native extension.

## Building and installing a wheel

Build wheels with the same environment that contains the local Basilisk and
SDK. `--no-isolation` ensures the plugin uses that SDK instead of resolving a
possibly different `bsk-sdk` from a package index.

```bash
cd $HOME/bsk_sdk/examples/rust-mrp-plugin
source $HOME/bsk_sdk/.venv/bin/activate
python -m build --wheel --no-isolation
python -m pip install --force-reinstall dist/rust_mrp_plugin-*.whl
```

The wheel contains `mrpRustController/__init__.py`, the SWIG wrapper
`mrpRustController.py`, and the platform-specific `_mrpRustController`
extension. It requires a compatible Basilisk installation at runtime.

### Test the installed wheel externally

Run the source test suite from a temporary directory so Python cannot import
the in-tree package. This verifies the package imported by the tests is the
wheel installed in the active environment.

```bash
cd $HOME/bsk_sdk/examples/rust-mrp-plugin
source $HOME/bsk_sdk/.venv/bin/activate
python -m pip install --force-reinstall dist/rust_mrp_plugin-*.whl

source_root="$PWD"
test_root="$(mktemp -d)"
mkdir -p "$test_root/suite"
cp -R "$source_root/mrpRustController/_UnitTest" "$test_root/suite/tests"
cp "$source_root/scenarioAttitudeFeedbackRust.py" "$test_root/"
cd "$test_root"
python -c "import mrpRustController; print(mrpRustController.__file__)"
python -m pytest --import-mode=importlib --rootdir="$test_root" \
  "$test_root/suite/tests" -v
```

---

## Running the scenario interactively

Running the script directly always shows plots (Basilisk convention):

```bash
cd $HOME/bsk_sdk/examples/rust-mrp-plugin
source $HOME/bsk_sdk/.venv/bin/activate
python -m pip install -e . --no-build-isolation
python scenarioAttitudeFeedbackRust.py
```

To suppress the interactive window (e.g. on a headless server):

```bash
python scenarioAttitudeFeedbackRust.py --no-plots
```

---

## Writing a new Rust module

See the Basilisk documentation's
[Writing a Rust Plugin](https://avslab.github.io/basilisk/develop/Plugins/writingRust.html)
page for the full reference (multiple/optional message ports, stateful
modules, the `BskModuleRuntime` mirror, etc.). Quick summary:

1. **Copy the structure** — duplicate `mrpRustController/` and rename.

2. **Edit `src/lib.rs`** — define your config struct with `#[repr(C)]`,
   including a mandatory `pub runtime: BskModuleRuntime` field (mirrors
   `SysModel`'s `moduleID`/`ModelTag`/`CallCounts`/`RNGSeed`; `build.rs` panics
   if it's missing), and implement `self_init`, `reset`, and `update`.  Use
   `///` doc comments on fields; they become Doxygen comments in the
   generated C header.

3. **Add to `CMakeLists.txt`**:

   ```cmake
   bsk_add_rust_module(
     TARGET     myModule
     MANIFEST   "${CMAKE_CURRENT_SOURCE_DIR}/myModule/Cargo.toml"
     OUTPUT_DIR "${PKG_DIR}"
   )
   ```

4. **Import in Python**:

   ```python
   from myModule import myModule
   mod = myModule.myModule()
   ```

---

## Generated vs. committed files

| File | Status | Notes |
|------|--------|-------|
| `_build/rust_headers/mrpRustController.h` | gitignored | generated by `bsk-build`; CMake tracks it as a Cargo byproduct |
| `_build/python/mrpRustController/mrpRustController.py` | gitignored | SWIG wrapper; regenerated by `cmake --build` |
| `_build/python/mrpRustController/_mrpRustController.so` | gitignored | compiled extension |

## Known limitations / experimental status

- Rust module support is **experimental**.  APIs may change.
- `bsk-messages` and `bsk-utilities` must be regenerated after Basilisk header
  syncs. `sync_headers.py` does this automatically when `bindgen` is available.
- Custom message types require a hand-written `*_C.h` C interface header.
- See `bsk-build` (`rust/bsk_build/`) for the shared code-generation logic.
