# rust-mrp-plugin

A Basilisk attitude controller implemented in Rust, demonstrating how to write
a BSK module using the `bsk-sdk`.  The Rust module replaces the built-in
C++ `mrpFeedback` module with a PD controller:

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

### 4 — Copy the Rust module CMake macro from Basilisk (once, or after a sync)

```bash
cd $HOME/bsk_sdk
python3 tools/sync_rust.py --basilisk-root $HOME/basilisk
```

This copies the `bsk_add_rust_module_sources` CMake macro. The Rust crates
(`bsk-build`, `bsk-messages`, `bsk-utilities`) aren't vendored into bsk-sdk —
`mrpRustController/Cargo.toml` depends on them directly from
`https://github.com/AVSLab/basilisk` (Basilisk's `develop` branch) via
Cargo's `git` support (see its comments).

**Rust module support hasn't landed in Basilisk yet**, so that dependency
won't resolve out of the box until it does — and, unlike a normal stale
dependency, this can't be worked around with a `[patch]`/`[source]`
override: both require the *original* source to resolve at least once
(have a matching `Cargo.toml` somewhere in it) before they'll redirect it,
and `https://github.com/AVSLab/basilisk`'s default branch has none yet.

Until that Basilisk PR merges, temporarily point the three `git = "..."`
entries in `mrpRustController/Cargo.toml` directly at the in-progress
branch instead (don't commit this edit):

```toml
bsk-messages = { git = "https://github.com/careweather/basilisk", branch = "feature/bsk-1482-rust-extensions" }
bsk-build    = { git = "https://github.com/careweather/basilisk", branch = "feature/bsk-1482-rust-extensions" }
# ...
bsk-build = { git = "https://github.com/careweather/basilisk", branch = "feature/bsk-1482-rust-extensions", features = ["codegen"] }
```

or, against a local checkout with those changes, use a `path` dependency
instead of `git` (see "Writing a Rust Plugin" in the Basilisk docs for why
`git`/`path` can't be combined in one entry).

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
the local checkout's package instead. This verifies the package imported by
the tests is the wheel installed in the active environment.

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
   if it's missing), and implement `reset` and `update` (and `init`, if the
   module needs non-zero parameter defaults before Python configures it).
   Use `///` doc comments on fields; they become Doxygen comments in the
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
- **Rust module support hasn't landed in Basilisk yet** (BSK-1482; the
  corresponding Basilisk PR is still open — see this PR's description for a
  link). Until it merges, `mrpRustController`'s dependency on
  `https://github.com/AVSLab/basilisk` won't resolve on its own — see the
  `[patch]` override in step 4 above. This PR is a draft for the same
  reason and will come out of draft once that PR merges (dropping the need
  for the override, and rebasing on whatever CI changes that adds).
- Custom message types require a hand-written `*_C.h` C interface header.
- `bsk-build`, `bsk-messages`, and `bsk-utilities` aren't published to
  crates.io yet, so `mrpRustController/Cargo.toml` depends on them via a
  Cargo `git` dependency on the Basilisk repository instead (see its
  comments) — this means a full clone of Basilisk on first build (cached by
  Cargo afterward, not repeated per build). This is a stopgap: once Rust
  module support is out of experimental status, these crates are expected to
  be published to crates.io instead.
- The `bsk_add_rust_module_sources` CMake macro
  (`cmake/bskAddRustModuleSources.cmake`) is copied from the Basilisk
  repository (`src/cmake/bskAddRustModuleSources.cmake` there) by
  `tools/sync_rust.py` — edit the Basilisk copy, not this one. Re-run that
  script after a Basilisk sync to pick up macro changes.
