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

# ---------------------------------------------------------------------------
# bsk_add_rust_module
#
# Register a Basilisk C module whose lifecycle functions (SelfInit_, Update_,
# Reset_) are implemented in a Rust crate.  The macro:
#
#   1. Locates cargo and builds the crate as a static library. bsk-build
#      (the crate's build.rs) generates the module's C header and SWIG .i
#      file as part of that build -- this macro just points SWIG at the
#      paths it uses (or accepts a hand-written .i file via INTERFACE).
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

  # ------------------------------------------------------------------
  # Validate required arguments
  # ------------------------------------------------------------------
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
  # Locate cargo
  # ------------------------------------------------------------------
  find_program(CARGO_EXECUTABLE cargo)
  if(NOT CARGO_EXECUTABLE)
    message(FATAL_ERROR
      "bsk_add_rust_module: 'cargo' not found.\n"
      "Install the Rust toolchain from https://rustup.rs/ and make sure "
      "'cargo' is on PATH.")
  endif()

  # ------------------------------------------------------------------
  # Resolve Cargo.toml and derive the staticlib output path
  # ------------------------------------------------------------------
  get_filename_component(_manifest "${RUST_MANIFEST}" ABSOLUTE)
  get_filename_component(_crate_dir "${_manifest}" DIRECTORY)

  set(_generates_header FALSE)
  if(NOT RUST_INTERFACE AND NOT RUST_HEADER)
    # bsk-build writes this Cargo byproduct outside the source tree. Keeping
    # its path predictable lets SWIG refer to it before the first cargo build.
    set(_generates_header TRUE)
    set(RUST_HEADER "${CMAKE_CURRENT_BINARY_DIR}/rust_headers/${RUST_TARGET}.h")
    message(STATUS
      "bsk_add_rust_module: HEADER not provided; "
      "generating bsk-build header at: ${RUST_HEADER}")
  endif()
  set(_extra_byproducts "")
  if(_generates_header)
    list(APPEND _extra_byproducts "${RUST_HEADER}")
    set(_header_env "BSK_HEADER_PATH=${RUST_HEADER}")
  else()
    set(_header_env "")
  endif()

  # bsk-build (the crate's build.rs) writes the SWIG .i file itself -- see
  # BSK_INTERFACE_PATH in its docs -- so this only has to point SWIG at a
  # predictable path, the same way it already does for HEADER above. There
  # is no CMake-side parsing of the crate's Rust source at all: cargo build
  # produces the .i file as a build byproduct, exactly like the .h file.
  set(_interface_env "")
  if(NOT RUST_INTERFACE)
    set(_gen_i "${CMAKE_CURRENT_BINARY_DIR}/${RUST_TARGET}_rust_wrap.i")
    set(_interface_env "BSK_INTERFACE_PATH=${_gen_i}")
    list(APPEND _extra_byproducts "${_gen_i}")
  endif()
  set(_header_byproducts BYPRODUCTS ${_extra_byproducts})

  if(NOT RUST_CARGO_PROFILE)
    set(RUST_CARGO_PROFILE "release")
  endif()

  # Cargo places the output in target/debug for profile "dev".
  if(RUST_CARGO_PROFILE STREQUAL "dev")
    set(_profile_dir "debug")
    set(_profile_flag "")
  else()
    set(_profile_dir "${RUST_CARGO_PROFILE}")
    set(_profile_flag "--${RUST_CARGO_PROFILE}")
  endif()

  # Derive the lib name: use CRATE_NAME if given, otherwise read the [lib] name
  # or [package] name from Cargo.toml (Cargo converts hyphens to underscores in
  # artifact names, matching the staticlib filename).
  if(RUST_CRATE_NAME)
    set(_lib_name "${RUST_CRATE_NAME}")
  else()
    # Try [lib] name first, fall back to [package] name.
    file(READ "${_manifest}" _cargo_toml_text)
    set(_lib_name "")
    if(_cargo_toml_text MATCHES "\\[lib\\][^\n]*\n[^\[]*name[ \t]*=[ \t]*\"([^\"]+)\"")
      set(_lib_name "${CMAKE_MATCH_1}")
    endif()
    if(NOT _lib_name AND _cargo_toml_text MATCHES "\\[package\\][^\n]*\n[^\[]*name[ \t]*=[ \t]*\"([^\"]+)\"")
      set(_lib_name "${CMAKE_MATCH_1}")
    endif()
    if(NOT _lib_name)
      message(FATAL_ERROR
        "bsk_add_rust_module: could not read crate name from ${_manifest}.\n"
        "Set CRATE_NAME explicitly.")
    endif()
    # Cargo replaces hyphens with underscores in staticlib filenames.
    string(REPLACE "-" "_" _lib_name "${_lib_name}")
  endif()

  set(_rust_target_dir "${CMAKE_CURRENT_BINARY_DIR}/rust_target")
  set(_rust_lib "${_rust_target_dir}/${_profile_dir}/lib${_lib_name}.a")

  # ------------------------------------------------------------------
  # Feature flags
  # ------------------------------------------------------------------
  set(_feature_args "")
  if(RUST_CARGO_FEATURES)
    list(JOIN RUST_CARGO_FEATURES "," _feat_str)
    set(_feature_args "--features" "${_feat_str}")
  endif()

  # ------------------------------------------------------------------
  # Custom command: build the Rust crate → staticlib
  #
  # Cargo handles its own incremental compilation.  We list Cargo.toml
  # and Cargo.lock as explicit dependencies; source file changes will
  # cause cargo to produce a newer .a (updating its mtime) which makes
  # the downstream link step re-run automatically.
  #
  # BSK_INCLUDE_DIR is set so that plugin build.rs scripts can call
  # bindgen against the vendored bsk_sdk headers without having bsk_sdk
  # installed in the Python environment at build time.
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

  set(_cargo_lock "${_crate_dir}/Cargo.lock")
  set(_dep_files "${_manifest}")
  if(EXISTS "${_cargo_lock}")
    list(APPEND _dep_files "${_cargo_lock}")
  endif()
  # Also depend on all Rust source files so cmake re-runs cargo when they change.
  file(GLOB_RECURSE _rust_sources "${_crate_dir}/src/*.rs")
  list(APPEND _dep_files ${_rust_sources})
  # build.rs changes should also trigger a rebuild.
  if(EXISTS "${_crate_dir}/build.rs")
    list(APPEND _dep_files "${_crate_dir}/build.rs")
  endif()

  add_custom_command(
    OUTPUT  "${_rust_lib}"
    ${_header_byproducts}
    COMMAND ${CMAKE_COMMAND} -E env
            "CARGO_TARGET_DIR=${_rust_target_dir}"
            "BSK_INCLUDE_DIR=${_bsk_sdk_include}"
            ${_header_env}
            ${_interface_env}
            ${RUST_CARGO_ENV}
            "${CARGO_EXECUTABLE}" build ${_profile_flag} ${_feature_args}
            --manifest-path "${_manifest}"
    DEPENDS ${_dep_files}
    WORKING_DIRECTORY "${_crate_dir}"
    COMMENT "Cargo: building Rust crate for BSK module '${RUST_TARGET}'"
    VERBATIM
  )

  set(_rust_target_name "_rust_build_${RUST_TARGET}")
  add_custom_target("${_rust_target_name}" DEPENDS "${_rust_lib}")

  if(NOT RUST_INTERFACE)
    set(RUST_INTERFACE "${_gen_i}")
  endif()

  # ------------------------------------------------------------------
  # Delegate to bsk_add_swig_module
  # No C/C++ SOURCES are needed: the Rust staticlib provides all three
  # SelfInit_/Update_/Reset_ symbols that CWrapper calls.
  # ------------------------------------------------------------------
  bsk_add_swig_module(
    TARGET      "${RUST_TARGET}"
    INTERFACE   "${RUST_INTERFACE}"
    INCLUDE_DIRS "${RUST_INCLUDE_DIRS}"
    LINK_LIBS   "${_rust_lib}" ${RUST_LINK_LIBS}
    DEPENDS     "${_rust_target_name}" ${RUST_DEPENDS}
    OUTPUT_DIR  "${RUST_OUTPUT_DIR}"
  )

  message(STATUS
    "bsk_add_rust_module: registered '${RUST_TARGET}' "
    "(Rust staticlib: ${_rust_lib})")
endfunction()
