# AGENTS.md

Guidance for coding agents working in this repository. This file applies to the
entire `bsk-sdk` repo.

## Repository Purpose

`bsk-sdk` is a Python wheel that lets external projects build
Basilisk-compatible SWIG extensions without vendoring the full Basilisk source
tree. The public contract is the installed wheel layout plus the CMake helpers
that downstream extension authors call:

- Python package: `src/bsk_sdk`
- CMake package: `cmake/bsk-sdkConfig.cmake.in`
- Extension helper: `cmake/bsk_add_swig_module.cmake`
- Message helper: `cmake/bsk_generate_messages.cmake`
- Consumer example: `examples/custom-atm-extension`
- Basilisk source input: `external/basilisk` submodule
- Sync tooling: `tools/sync_all.py` and sibling `tools/sync_*.py` scripts

Prefer changes that preserve the downstream extension experience:

```cmake
find_package(bsk-sdk CONFIG REQUIRED)
bsk_add_swig_module(...)
bsk_generate_messages(...)
```

## Worktree And Branch Discipline

- Start by checking `git status --short --branch` and noting whether
  `external/basilisk` is modified. Do not reset, checkout, or otherwise clean
  user/submodule changes unless explicitly asked.
- Use focused branches for agent work. In this Codex workspace, prefer
  `codex/<short-topic>` unless the user requests another branch name.
- Do not work directly on `master` or `develop` for feature/fix changes unless
  the user explicitly asks.
- Keep PRs draft until the relevant build/test commands below have been run or
  the skipped checks are clearly documented.
- PR descriptions should call out:
  - The affected surface: packaging, CMake/SWIG, sync tooling, example extension,
    CI, or docs.
  - The Basilisk version or submodule commit, if it changed.
  - The local verification commands and any skipped checks.
  - Any downstream compatibility impact for extension authors.

## Generated And Vendored Boundaries

The SDK vendors a curated subset of Basilisk, but the generated/synced artifact
directories are ignored by git and should normally be recreated locally:

- `src/bsk_sdk/include/Basilisk/`
- `src/bsk_sdk/include/cMsgCInterface/`
- `src/bsk_sdk/include_compat/`
- `src/bsk_sdk/arch_min/`
- `src/bsk_sdk/arch_utilities/`
- `src/bsk_sdk/runtime_min/`
- `src/bsk_sdk/swig/`
- `tools/msgAutoSource/`

Use the sync scripts rather than hand-editing generated Basilisk copies:

```bash
git submodule update --init --recursive
python3 tools/sync_all.py
```

For an intentional Basilisk update:

```bash
cd external/basilisk
git fetch
git checkout <tag-or-commit>
cd ../..
python3 tools/sync_all.py
```

After a sync, check that `src/bsk_sdk/_bsk_version.txt` matches the Basilisk
source and that any submodule pointer change is intentional. Do not stage
ignored generated directories unless a maintainer specifically asks for a
release artifact workflow that requires it.

## Build And Test Commands

Use the smallest verification set that covers the changed surface, then report
exactly what ran.

Package smoke path:

```bash
python -m pip install build
BSK_SDK_AUTO_SYNC=0 python -m build --wheel -o dist
python -m pip install dist/*.whl pytest --force-reinstall
pytest tests/test_smoke.py -v
```

Downstream extension path:

```bash
python -m pip install dist/*.whl --force-reinstall
python -c "import bsk_sdk, subprocess, sys; \
subprocess.run([sys.executable, '-m', 'pip', 'install', \
f'bsk[all]=={bsk_sdk.bsk_version()}'], check=True)"
python -c "import Basilisk; print(Basilisk.__file__)"
python -m pip install build scikit-build-core
python -m build --wheel --no-isolation -o extension-dist examples/custom-atm-extension
python -m pip install extension-dist/*.whl pytest --force-reinstall
pytest examples/custom-atm-extension/customExponentialAtmosphere/_UnitTest/test_customExponentialAtmosphere.py -v
```

Sync path:

```bash
python3 tools/sync_all.py
```

Notes:

- A local wheel build may need network access if CMake must fetch Eigen3 and it
  is not already available.
- The example extension build intentionally uses `--no-isolation` so it tests the
  just-built SDK wheel instead of accidentally pulling a stale PyPI package.
- Install the exact `bsk[all]` version reported by `bsk_sdk.bsk_version()` and
  confirm that `Basilisk` imports before running the example extension test. The
  test uses `pytest.importorskip`, so a missing BSK installation can otherwise
  produce a successful pytest exit without exercising the extension.
- CI runs Linux, macOS, and Windows against the minimum and maximum supported
  Python versions. Review local-only changes with that matrix in mind.

## Coding Conventions

- Keep new repository text and source edits ASCII unless the surrounding file
  already uses non-ASCII for a clear reason.
- Follow the existing ISC license header style for new source files.
- Python code should use `pathlib`, typed signatures where practical, and
  `subprocess.run(..., check=True)` for required commands.
- CMake code must stay cross-platform. Quote paths, avoid Unix-only assumptions,
  handle multi-config generators, and prefer imported targets like
  `Python3::Module` and `Eigen3::Eigen`.
- Keep `pyproject.toml`, `CMakeLists.txt`, installed package paths, and smoke
  tests in sync. If a file must ship in the wheel or sdist, update the install
  rules and `tool.scikit-build.sdist.include`/`exclude` as needed.
- Avoid adding extension-author requirements that contradict the core promise:
  SDK sources, runtime-minimal sources, and built-in C message interface sources
  should be handled by `bsk_add_swig_module`, not manually wired by consumers.

## Lessons Learned For PR Review

When reviewing branches or PRs, look first for regressions in the installed
contract and the consumer build, not just whether the repository build passes.

- Version checks must compare Basilisk versions as strings. CMake
  `VERSION_EQUAL` can treat pre-release suffixes incorrectly; use `STREQUAL`
  when validating `bsk-sdk` versus installed `bsk`.
- SWIG runtime epochs matter. Keep the `swig==4.4.1` dependency, the
  pip-installed SWIG discovery, and the SWIG runtime mismatch diagnostics
  aligned with the Basilisk wheel.
- Do not globally guard all CMake dependency setup. `find_package(SWIG)`,
  `include(${SWIG_USE_FILE})`, and Python/Eigen target setup must run in the
  function scope that calls `swig_add_library`.
- Generated `.i` files for message bindings must exist at configure time so
  CMake's UseSWIG dependency scanning can see them. Preserve the configure-time
  bootstrap plus build-time `add_custom_command` pattern.
- Message binding imports have ordering requirements. Generated messaging
  packages should be imported before module wrappers that depend on custom
  `Message<T>` and `Recorder<T>` proxy registration.
- Windows and multi-config generators are easy to break. Check output
  directories, `.bat` wrapper behavior, path quoting, and cache variable usage.
- Pre-release SDKs (`alpha`, `beta`, `rc`) intentionally have softer version
  behavior than release SDKs. Release mismatches should fail loudly; pre-release
  mismatches should warn when that is the intended compatibility policy.
- Adding or moving installed files requires three-way review: CMake install
  rules, Python path helper APIs, and `tests/test_smoke.py` assertions.
- Example extension failures are usually the most realistic signal for downstream
  users. Treat `examples/custom-atm-extension` as a compatibility test, not just
  sample code.

## Review Checklist

For every PR, answer these before approving:

- Does the wheel still expose the expected package root, include directories,
  CMake config files, SWIG directory, tools directory, and SDK source dirs?
- If the CMake helpers changed, does the example extension still build and import
  on a clean install?
- If sync tooling changed, does `python3 tools/sync_all.py` still stamp the BSK
  version and recreate all required artifact directories/files?
- If dependencies changed, are `pyproject.toml`, CI, example extension metadata,
  and CMake diagnostics consistent?
- If `external/basilisk` changed, is the submodule pointer intentional and is
  the corresponding version impact documented?
- Are skipped tests explained with the concrete blocker, such as missing BSK
  wheels, local platform limits, or network restrictions?
