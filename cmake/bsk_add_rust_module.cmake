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

if(NOT DEFINED BSK_SDK_RUST_CMAKE_DIR)
  message(FATAL_ERROR "bsk-sdk did not configure its synchronized Rust CMake directory")
endif()
include("${BSK_SDK_RUST_CMAKE_DIR}/bskRustSupportVersions.cmake")
include("${BSK_SDK_RUST_CMAKE_DIR}/bskAddRustModuleSources.cmake")

function(_bsk_sdk_find_cargo out_var)
  find_program(_bsk_sdk_cargo NAMES cargo)
  if(NOT _bsk_sdk_cargo)
    message(FATAL_ERROR
      "This extension defines a Rust module, but Cargo was not found on PATH. "
      "Install Rust ${BSK_RUST_MIN_VERSION} or newer from https://rustup.rs/ "
      "and configure the extension again. C/C++-only extensions do not need Rust.")
  endif()
  set(${out_var} "${_bsk_sdk_cargo}" PARENT_SCOPE)
endfunction()

function(_bsk_sdk_register_rust_metadata_dependencies metadata manifest)
  cmake_path(CONVERT "${manifest}" TO_CMAKE_PATH_LIST _manifest NORMALIZE)
  set(_dependencies "${_manifest}")
  get_filename_component(_workspace_dir "${_manifest}" DIRECTORY)
  list(APPEND _dependencies "${_workspace_dir}/Cargo.lock")

  string(JSON _package_count LENGTH "${metadata}" packages)
  if(_package_count GREATER 0)
    math(EXPR _last_package "${_package_count} - 1")
    foreach(_package_index RANGE 0 ${_last_package})
      string(JSON _package_manifest GET "${metadata}"
             packages ${_package_index} manifest_path)
      cmake_path(CONVERT "${_package_manifest}"
                 TO_CMAKE_PATH_LIST _package_manifest NORMALIZE)
      list(APPEND _dependencies "${_package_manifest}")
    endforeach()
  endif()

  list(REMOVE_DUPLICATES _dependencies)
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${_dependencies})
endfunction()

function(_bsk_sdk_rust_metadata manifest out_var)
  get_filename_component(_manifest "${manifest}" ABSOLUTE)
  if(NOT EXISTS "${_manifest}")
    message(FATAL_ERROR "Rust workspace manifest not found: ${_manifest}")
  endif()
  _bsk_sdk_find_cargo(_cargo)
  execute_process(
    COMMAND "${_cargo}" metadata --locked --no-deps --format-version 1
            --manifest-path "${_manifest}"
    RESULT_VARIABLE _result
    OUTPUT_VARIABLE _metadata
    ERROR_VARIABLE _error
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_STRIP_TRAILING_WHITESPACE
  )
  if(NOT _result EQUAL 0)
    message(FATAL_ERROR
      "Cargo metadata failed for ${_manifest}. Ensure Cargo.lock is current:\n"
      "${_error}")
  endif()
  _bsk_sdk_register_rust_metadata_dependencies("${_metadata}" "${_manifest}")
  set(${out_var} "${_metadata}" PARENT_SCOPE)
endfunction()

function(_bsk_sdk_static_library_target metadata package_index out_var)
  string(JSON _target_count LENGTH "${metadata}" packages ${package_index} targets)
  if(_target_count EQUAL 0)
    message(FATAL_ERROR "A marked Basilisk Rust package has no Cargo targets")
  endif()
  math(EXPR _last_target "${_target_count} - 1")
  set(_static_targets "")
  foreach(_target_index RANGE 0 ${_last_target})
    string(JSON _crate_type_count LENGTH "${metadata}"
           packages ${package_index} targets ${_target_index} crate_types)
    if(_crate_type_count GREATER 0)
      math(EXPR _last_crate_type "${_crate_type_count} - 1")
      foreach(_crate_type_index RANGE 0 ${_last_crate_type})
        string(JSON _crate_type GET "${metadata}"
               packages ${package_index} targets ${_target_index}
               crate_types ${_crate_type_index})
        if(_crate_type STREQUAL "staticlib")
          string(JSON _target_name GET "${metadata}"
                 packages ${package_index} targets ${_target_index} name)
          list(APPEND _static_targets "${_target_name}")
        endif()
      endforeach()
    endif()
  endforeach()
  list(REMOVE_DUPLICATES _static_targets)
  list(LENGTH _static_targets _static_target_count)
  if(NOT _static_target_count EQUAL 1)
    message(FATAL_ERROR
      "A Basilisk Rust module package must define exactly one staticlib target; "
      "found ${_static_target_count}")
  endif()
  list(GET _static_targets 0 _static_target)
  set(${out_var} "${_static_target}" PARENT_SCOPE)
endfunction()

function(_bsk_sdk_validate_support_dependencies metadata package_index)
  string(JSON _dependency_count ERROR_VARIABLE _dependency_error
         LENGTH "${metadata}" packages ${package_index} dependencies)
  if(_dependency_error)
    message(FATAL_ERROR "A Basilisk Rust module package has no dependency metadata")
  endif()
  set(_has_bsk_build FALSE)
  set(_has_bsk_messages FALSE)
  if(_dependency_count GREATER 0)
    math(EXPR _last_dependency "${_dependency_count} - 1")
    foreach(_dependency_index RANGE 0 ${_last_dependency})
      string(JSON _dependency_name GET "${metadata}"
             packages ${package_index} dependencies ${_dependency_index} name)
      if(NOT _dependency_name MATCHES "^bsk-(build|messages|utilities)$")
        continue()
      endif()
      string(JSON _dependency_requirement GET "${metadata}"
             packages ${package_index} dependencies ${_dependency_index} req)
      if(NOT _dependency_requirement STREQUAL "=${BSK_RUST_SUPPORT_CRATE_VERSION}")
        message(FATAL_ERROR
          "${_dependency_name} must use the exact version "
          "=${BSK_RUST_SUPPORT_CRATE_VERSION}; Cargo metadata reports "
          "${_dependency_requirement}")
      endif()
      if(_dependency_name STREQUAL "bsk-build")
        set(_has_bsk_build TRUE)
      elseif(_dependency_name STREQUAL "bsk-messages")
        set(_has_bsk_messages TRUE)
      endif()
    endforeach()
  endif()
  if(NOT _has_bsk_build OR NOT _has_bsk_messages)
    message(FATAL_ERROR
      "A Basilisk Rust module must depend on exact versions of bsk-build and "
      "bsk-messages matching bsk-sdk ${BSK_RUST_SUPPORT_CRATE_VERSION}")
  endif()
endfunction()

function(_bsk_sdk_rust_modules_from_metadata metadata out_targets out_manifests)
  string(JSON _package_count LENGTH "${metadata}" packages)
  set(_targets "")
  set(_manifests "")
  if(_package_count GREATER 0)
    math(EXPR _last_package "${_package_count} - 1")
    foreach(_package_index RANGE 0 ${_last_package})
      string(JSON _marker_type ERROR_VARIABLE _marker_error TYPE "${metadata}"
             packages ${_package_index} metadata basilisk module)
      if(_marker_error OR NOT _marker_type STREQUAL "BOOLEAN")
        continue()
      endif()
      string(JSON _is_module GET "${metadata}"
             packages ${_package_index} metadata basilisk module)
      if(NOT _is_module)
        continue()
      endif()
      string(JSON _package_manifest GET "${metadata}"
             packages ${_package_index} manifest_path)
      _bsk_sdk_validate_support_dependencies("${metadata}" ${_package_index})
      _bsk_sdk_static_library_target("${metadata}" ${_package_index} _target)
      list(APPEND _targets "${_target}")
      list(APPEND _manifests "${_package_manifest}")
    endforeach()
  endif()
  set(${out_targets} "${_targets}" PARENT_SCOPE)
  set(${out_manifests} "${_manifests}" PARENT_SCOPE)
endfunction()

function(_bsk_sdk_find_python_libclang out_var)
  execute_process(
    COMMAND "${Python3_EXECUTABLE}" -c
      "import bsk_sdk; print(bsk_sdk.rust_libclang_dir(), end='')"
    RESULT_VARIABLE _result
    OUTPUT_VARIABLE _directory
    ERROR_VARIABLE _error
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_STRIP_TRAILING_WHITESPACE
  )
  if(NOT _result EQUAL 0 OR NOT IS_DIRECTORY "${_directory}")
    message(FATAL_ERROR
      "Rust message binding generation could not locate the libclang Python "
      "package supplied by bsk-sdk.\n${_error}")
  endif()
  set(${out_var} "${_directory}" PARENT_SCOPE)
endfunction()

function(_bsk_sdk_rust_message_directories out_var)
  set(_directories "${BSK_SDK_C_MSG_INTERFACE_DIR}")
  get_property(_extension_directories GLOBAL PROPERTY BSK_SDK_EXTENSION_C_MSG_DIRS)
  list(APPEND _directories ${_extension_directories} ${ARGN})
  list(REMOVE_ITEM _directories "")
  list(REMOVE_DUPLICATES _directories)
  foreach(_directory IN LISTS _directories)
    if(NOT IS_DIRECTORY "${_directory}")
      message(FATAL_ERROR "Rust C-message interface directory not found: ${_directory}")
    endif()
  endforeach()
  set(${out_var} "${_directories}" PARENT_SCOPE)
endfunction()

# Keep Windows path-list semicolons out of Corrosion's CMake argument lists by
# passing Cargo one response-file path instead of the directory list itself.
function(_bsk_sdk_write_rust_message_directory_file out_var target)
  set(_directories ${ARGN})
  if(NOT _directories)
    message(FATAL_ERROR "No Rust C-message interface directories were provided")
  endif()

  set(_response_directory "${CMAKE_CURRENT_BINARY_DIR}/rust/cmsg")
  set(_response_file "${_response_directory}/${target}.txt")
  file(MAKE_DIRECTORY "${_response_directory}")
  string(JOIN "\n" _response_contents ${_directories})
  file(WRITE "${_response_file}" "${_response_contents}\n")
  set(${out_var} "${_response_file}" PARENT_SCOPE)
endfunction()

function(bsk_add_rust_module)
  set(_one TARGET MANIFEST OUTPUT_DIR)
  set(_multi C_MSG_DIRS CARGO_FEATURES)
  cmake_parse_arguments(BSK "" "${_one}" "${_multi}" ${ARGN})
  if(NOT BSK_TARGET OR NOT BSK_MANIFEST)
    message(FATAL_ERROR "bsk_add_rust_module requires TARGET and MANIFEST")
  endif()
  if(NOT BSK_OUTPUT_DIR)
    set(BSK_OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}")
  endif()

  _bsk_find_build_deps()
  _bsk_resolve_sdk_sources(_sdk_runtime)
  _bsk_sdk_rust_message_directories(_c_message_dirs ${BSK_C_MSG_DIRS})
  _bsk_sdk_write_rust_message_directory_file(
    _c_message_file "${BSK_TARGET}" ${_c_message_dirs})

  set(_cargo_env
      "BSK_CMSG_DIRS_FILE=${_c_message_file}"
      "BSK_SRC_ROOT=${BSK_SDK_INCLUDE_DIR}/Basilisk")
  if(UNIX AND NOT APPLE AND CMAKE_C_IMPLICIT_INCLUDE_DIRECTORIES)
    cmake_path(CONVERT "${CMAKE_C_IMPLICIT_INCLUDE_DIRECTORIES}"
               TO_NATIVE_PATH_LIST _system_include_dirs NORMALIZE)
    list(APPEND _cargo_env "BSK_C_SYSTEM_INCLUDE_DIRS=${_system_include_dirs}")
  endif()
  if(NOT APPLE)
    _bsk_sdk_find_python_libclang(_libclang_dir)
    list(APPEND _cargo_env "LIBCLANG_PATH=${_libclang_dir}")
  endif()

  set(_artifact_root "${CMAKE_CURRENT_BINARY_DIR}/rust")
  bsk_add_rust_module_sources(
    TARGET "${BSK_TARGET}"
    MANIFEST "${BSK_MANIFEST}"
    HEADER "${_artifact_root}/include/${BSK_TARGET}.h"
    INTERFACE "${_artifact_root}/swig/${BSK_TARGET}_rust_wrap.i"
    INCLUDE_DIR "${BSK_SDK_INCLUDE_DIR}/Basilisk"
    CARGO_FEATURES ${BSK_CARGO_FEATURES}
    CARGO_ENV ${_cargo_env}
    OUT_LINK_TARGET_VAR _rust_link_target
    OUT_HEADER_VAR _rust_header
    OUT_INTERFACE_VAR _rust_interface
    OUT_BUILD_TARGET_VAR _rust_build_target
  )
  if(DEFINED Rust_VERSION AND Rust_VERSION VERSION_LESS BSK_RUST_MIN_VERSION)
    message(FATAL_ERROR
      "Rust ${Rust_VERSION} is too old; bsk-sdk requires Rust "
      "${BSK_RUST_MIN_VERSION} or newer")
  endif()

  set(_swig_target "_bsk_sdk_python_${BSK_TARGET}")
  set_source_files_properties("${_rust_interface}" PROPERTIES GENERATED TRUE)
  set_property(SOURCE "${_rust_interface}" PROPERTY CPLUSPLUS ON)
  set_property(SOURCE "${_rust_interface}" PROPERTY USE_TARGET_INCLUDE_DIRECTORIES TRUE)
  set(BSK_INCLUDE_DIRS "")
  foreach(_directory IN LISTS _c_message_dirs)
    get_filename_component(_include_root "${_directory}" DIRECTORY)
    list(APPEND BSK_INCLUDE_DIRS "${_include_root}")
  endforeach()
  _bsk_collect_swig_flags(_swig_flags)
  set_property(SOURCE "${_rust_interface}" PROPERTY SWIG_FLAGS ${_swig_flags})

  set(_wrapper_dir "${_artifact_root}/swig/${BSK_TARGET}")
  file(MAKE_DIRECTORY "${_wrapper_dir}")
  swig_add_library(
    "${_swig_target}"
    LANGUAGE python
    TYPE MODULE
    SOURCES "${_rust_interface}"
    OUTPUT_DIR "${BSK_OUTPUT_DIR}"
    OUTFILE_DIR "${_wrapper_dir}"
  )
  set_target_properties("${_swig_target}" PROPERTIES OUTPUT_NAME "${BSK_TARGET}")
  _bsk_add_rust_windows_exports("${_swig_target}" "${BSK_TARGET}")
  set_property(TARGET "${_swig_target}" APPEND PROPERTY SWIG_DEPENDS
    "${_rust_header}"
    "${BSK_SDK_SWIG_DIR}/architecture/_GeneralModuleFiles/swig_c_wrap.i")
  add_dependencies("${_swig_target}" "${_rust_build_target}")
  if(TARGET "${_swig_target}_swig_compilation")
    add_dependencies("${_swig_target}_swig_compilation" "${_rust_build_target}")
  endif()

  _bsk_configure_swig_target(
    "${_swig_target}"
    "${BSK_OUTPUT_DIR}"
    "${_rust_link_target};${_sdk_runtime}"
    "${BSK_INCLUDE_DIRS};${_artifact_root}/include"
  )

  if(UNIX)
    add_custom_command(
      TARGET "${_swig_target}"
      POST_BUILD
      COMMAND "${CMAKE_COMMAND}"
              "-DBSK_RUST_MODULE_FILE=$<TARGET_FILE:${_swig_target}>"
              "-DBSK_NM_EXECUTABLE=${CMAKE_NM}"
              -P "${BSK_SDK_RUST_CMAKE_DIR}/bskCheckRustModuleSymbols.cmake"
      COMMENT "Checking Rust module linkage for '${BSK_TARGET}'"
      VERBATIM
    )
  endif()
endfunction()

function(bsk_add_rust_workspace)
  set(_one MANIFEST OUTPUT_DIR)
  set(_multi C_MSG_DIRS)
  cmake_parse_arguments(BSK "" "${_one}" "${_multi}" ${ARGN})
  if(NOT BSK_MANIFEST)
    message(FATAL_ERROR "bsk_add_rust_workspace requires MANIFEST")
  endif()
  _bsk_sdk_rust_metadata("${BSK_MANIFEST}" _metadata)
  string(JSON _package_count LENGTH "${_metadata}" packages)
  if(_package_count EQUAL 0)
    message(FATAL_ERROR "The Rust workspace contains no packages")
  endif()

  _bsk_sdk_rust_modules_from_metadata("${_metadata}" _targets _manifests)
  list(LENGTH _targets _module_count)
  if(_module_count EQUAL 0)
    message(FATAL_ERROR
      "No Rust workspace package has [package.metadata.basilisk] module = true")
  endif()

  math(EXPR _last_module "${_module_count} - 1")
  foreach(_module_index RANGE 0 ${_last_module})
    list(GET _targets ${_module_index} _target)
    list(GET _manifests ${_module_index} _package_manifest)
    bsk_add_rust_module(
      TARGET "${_target}"
      MANIFEST "${_package_manifest}"
      OUTPUT_DIR "${BSK_OUTPUT_DIR}"
      C_MSG_DIRS ${BSK_C_MSG_DIRS}
    )
  endforeach()
  message(STATUS "bsk-sdk: configured ${_module_count} Rust extension module(s)")
endfunction()
