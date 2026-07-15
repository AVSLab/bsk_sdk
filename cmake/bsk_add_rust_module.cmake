#
#  ISC License
#
#  Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
#
#  Permission to use, copy, modify, and/or distribute this software for any
#  purpose with or without fee is hereby granted, provided that the above
#  copyright notice and this permission notice appear in all copies.
#
#  THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
#  WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
#  ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
#  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
#  ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
#  OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#

include_guard(GLOBAL)

if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/bsk_add_swig_module.cmake")
  include("${CMAKE_CURRENT_LIST_DIR}/bsk_add_swig_module.cmake")
endif()

# bsk_add_rust_module_sources (cargo build -> .a/.h/.i) is Basilisk-core
# tooling, vendored here the same way headers/SWIG files are -- see
# tools/sync_rust.py. Basilisk core has no notion of "wheel", so this file
# is only the packaging half: resolve the SDK's own header include path,
# call the vendored macro to build the crate, then hand its outputs to
# bsk_add_swig_module.
if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/bskAddRustModuleSources.cmake")
  include("${CMAKE_CURRENT_LIST_DIR}/bskAddRustModuleSources.cmake")
endif()

# ---------------------------------------------------------------------------
# bsk_add_rust_module
#
# Register a Basilisk C module whose lifecycle functions (SelfInit_, Update_,
# Reset_) are implemented in a Rust crate.  The macro:
#
#   1. Calls bsk_add_rust_module_sources (vendored from Basilisk core) to
#      build the crate and locate/generate its C header + SWIG .i file.
#   2. Delegates to bsk_add_swig_module, linking the Rust staticlib in.
#
# Required arguments
# ------------------
#   TARGET      CMake target name (becomes the Python module name).
#   MANIFEST    Path to the crate's Cargo.toml.
#   OUTPUT_DIR  Directory where the compiled Python wheel extension lands.
#
# Optional arguments (header)
# ---------------------------
#   HEADER      Path to the module's .h file.  When omitted (recommended for
#               modules that use bsk-build), it is generated under the CMake
#               build tree.  Provide HEADER explicitly only when using a
#               hand-written header or a non-standard path.
#
# Optional arguments
# ------------------
#   INTERFACE      Hand-written .i file; overrides bsk-build's generated one.
#   CRATE_NAME     Override the crate lib name when it differs from TARGET
#                  (underscores in TARGET are already mapped to underscores).
#   CARGO_PROFILE  "release" (default) or "dev".
#   CARGO_FEATURES Cargo feature flags to enable (list).
#   CARGO_ENV      Extra environment variable assignments forwarded to cargo
#                  (e.g. "RUSTFLAGS=-C opt-level=3").
#   INCLUDE_DIRS   Additional include directories for the SWIG module.
#   LINK_LIBS      Additional libraries to link alongside the Rust staticlib.
#   DEPENDS        Additional CMake targets this module depends on.
#
# Example
# -------
#   bsk_add_rust_module(
#     TARGET      mrpRustController
#     MANIFEST    "${CMAKE_CURRENT_SOURCE_DIR}/mrpRustController/Cargo.toml"
#     OUTPUT_DIR  "${PKG_DIR}"
#   )
#   # HEADER is optional: bsk-build generates it in the CMake build tree.
# ---------------------------------------------------------------------------
function(bsk_add_rust_module)
  set(_one  TARGET HEADER MANIFEST OUTPUT_DIR INTERFACE CRATE_NAME CARGO_PROFILE)
  set(_multi CARGO_FEATURES CARGO_ENV INCLUDE_DIRS LINK_LIBS DEPENDS)
  cmake_parse_arguments(RUST "" "${_one}" "${_multi}" ${ARGN})

  if(NOT RUST_TARGET)
    message(FATAL_ERROR "bsk_add_rust_module: TARGET is required")
  endif()
  if(NOT RUST_MANIFEST)
    message(FATAL_ERROR "bsk_add_rust_module: MANIFEST (path to Cargo.toml) is required")
  endif()
  if(NOT RUST_OUTPUT_DIR)
    set(RUST_OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}")
  endif()

  # ------------------------------------------------------------------
  # Resolve the Basilisk include root a module's own build.rs may need
  # (e.g. for bindgen against a custom message type). bsk_add_rust_module_
  # sources defaults BSK_INCLUDE_DIR to CMAKE_SOURCE_DIR, which here is the
  # plugin's own source root, not Basilisk's -- point it at bsk-sdk's own
  # copied header tree (or an installed bsk_sdk package's) instead.
  # ------------------------------------------------------------------
  execute_process(
    COMMAND "${Python3_EXECUTABLE}" -c
      "import bsk_sdk; print(bsk_sdk.include_dir(), end='')"
    OUTPUT_VARIABLE _bsk_sdk_include
    RESULT_VARIABLE _bsk_sdk_result
    ERROR_QUIET
  )
  if(NOT _bsk_sdk_result EQUAL 0 OR NOT _bsk_sdk_include)
    # Fall back to the include directory adjacent to this cmake file
    # (works when bsk_sdk is used from source without being installed).
    get_filename_component(_bsk_sdk_include
      "${CMAKE_CURRENT_LIST_DIR}/../src/bsk_sdk/include" ABSOLUTE)
  endif()

  bsk_add_rust_module_sources(
    TARGET         "${RUST_TARGET}"
    MANIFEST       "${RUST_MANIFEST}"
    HEADER         "${RUST_HEADER}"
    INTERFACE      "${RUST_INTERFACE}"
    CRATE_NAME     "${RUST_CRATE_NAME}"
    CARGO_PROFILE  "${RUST_CARGO_PROFILE}"
    CARGO_FEATURES ${RUST_CARGO_FEATURES}
    CARGO_ENV      ${RUST_CARGO_ENV}
    INCLUDE_DIR    "${_bsk_sdk_include}"
    OUT_LIB_VAR          _rust_lib
    OUT_HEADER_VAR       _rust_header
    OUT_INTERFACE_VAR    _rust_interface
    OUT_BUILD_TARGET_VAR _rust_target_name
  )

  # ------------------------------------------------------------------
  # Delegate to bsk_add_swig_module
  # No C/C++ SOURCES are needed: the Rust staticlib provides all three
  # SelfInit_/Update_/Reset_ symbols that RustWrapper calls.
  # ------------------------------------------------------------------
  bsk_add_swig_module(
    TARGET      "${RUST_TARGET}"
    INTERFACE   "${_rust_interface}"
    INCLUDE_DIRS "${RUST_INCLUDE_DIRS}"
    LINK_LIBS   "${_rust_lib}" ${RUST_LINK_LIBS}
    DEPENDS     "${_rust_target_name}" ${RUST_DEPENDS}
    OUTPUT_DIR  "${RUST_OUTPUT_DIR}"
  )

  message(STATUS
    "bsk_add_rust_module: registered '${RUST_TARGET}' "
    "(Rust staticlib: ${_rust_lib})")
endfunction()
