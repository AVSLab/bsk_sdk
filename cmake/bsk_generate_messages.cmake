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

# Locate the msgAutoSource directory that ships the message generators.  These
# scripts must be present — the JSON and equality generators were added in BSK
# 2.11 and are required by bsk_generate_messages().
function(_bsk_resolve_msg_autosource_dir out_var)
  if(DEFINED BSK_SDK_MSG_AUTOSOURCE_DIR
      AND EXISTS "${BSK_SDK_MSG_AUTOSOURCE_DIR}/generateSWIGModules.py"
      AND EXISTS "${BSK_SDK_MSG_AUTOSOURCE_DIR}/generatePayloadMetaJson.py"
      AND EXISTS "${BSK_SDK_MSG_AUTOSOURCE_DIR}/generatePayloadEqualityHeader.py")
    set(${out_var} "${BSK_SDK_MSG_AUTOSOURCE_DIR}" PARENT_SCOPE)
    return()
  endif()

  if(DEFINED bsk-sdk_DIR AND EXISTS "${bsk-sdk_DIR}")
    set(_cmake_dir "${bsk-sdk_DIR}")
  else()
    set(_cmake_dir "${CMAKE_CURRENT_FUNCTION_LIST_DIR}")
  endif()

  get_filename_component(_pkg_root "${_cmake_dir}/../../.." REALPATH)

  set(_candidates
    "${_pkg_root}/tools/msgAutoSource"
    "${_cmake_dir}/../tools/msgAutoSource"
  )

  foreach(_cand IN LISTS _candidates)
    if(EXISTS "${_cand}/generateSWIGModules.py"
        AND EXISTS "${_cand}/generatePayloadMetaJson.py"
        AND EXISTS "${_cand}/generatePayloadEqualityHeader.py")
      set(${out_var} "${_cand}" PARENT_SCOPE)
      return()
    endif()
  endforeach()

  string(JOIN "\n  " _cand_list ${_candidates})
  message(FATAL_ERROR
    "bsk-sdk message generators not found.\n\n"
    "Looked for generateSWIGModules.py, generatePayloadMetaJson.py, and "
    "generatePayloadEqualityHeader.py under:\n"
    "  ${_cand_list}\n\n"
    "Re-sync the SDK tools (requires BSK >= 2.11):\n"
    "  python3 tools/sync_all.py --sync-submodules\n\n"
    "Or set BSK_SDK_MSG_AUTOSOURCE_DIR explicitly."
  )
endfunction()

function(bsk_generate_messages)
  set(options GENERATE_C_INTERFACE)
  set(oneValueArgs OUTPUT_DIR OUT_VAR)
  set(multiValueArgs MSG_HEADERS INCLUDE_DIRS SWIG_INCLUDE_DIRS TARGET_LINK_LIBS)
  cmake_parse_arguments(BSK "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

  if(NOT BSK_MSG_HEADERS)
    message(FATAL_ERROR "bsk_generate_messages requires MSG_HEADERS")
  endif()

  if(NOT BSK_OUTPUT_DIR)
    set(BSK_OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}")
  endif()

  _bsk_find_build_deps()

  _bsk_resolve_sdk_sources(_bsk_sdk_link_libs)
  set(BSK_TARGET_LINK_LIBS ${BSK_TARGET_LINK_LIBS} ${_bsk_sdk_link_libs})

  _bsk_collect_swig_flags(_swig_flags)
  _bsk_resolve_msg_autosource_dir(_msg_autosrc)

  set(_gen_swig "${_msg_autosrc}/generateSWIGModules.py")
  set(_gen_meta "${_msg_autosrc}/generatePayloadMetaJson.py")
  set(_gen_eq "${_msg_autosrc}/generatePayloadEqualityHeader.py")
  set(_auto_root "${CMAKE_CURRENT_BINARY_DIR}/autoSource")
  set(_json_dir "${_auto_root}/cMsgMeta")
  file(MAKE_DIRECTORY "${_json_dir}")

  set(_generated_targets "")
  set(_gen_c "False")
  if(BSK_GENERATE_C_INTERFACE)
    set(_gen_c "True")
  endif()

  foreach(_hdr IN LISTS BSK_MSG_HEADERS)
    get_filename_component(_hdr_abs "${_hdr}" ABSOLUTE)
    get_filename_component(_payload_name "${_hdr_abs}" NAME_WE)
    get_filename_component(_hdr_dir "${_hdr_abs}" DIRECTORY)

    # Detect C vs C++ based on GENERATE_C_INTERFACE flag
    if(BSK_GENERATE_C_INTERFACE)
      set(_clang_lang "c")
    else()
      set(_clang_lang "c++")
    endif()

    # Generate struct metadata JSON from the header using libclang
    set(_meta_out "${_json_dir}/${_payload_name}.json")
    set(_depfile "${_json_dir}/${_payload_name}.d")
    add_custom_command(
      OUTPUT "${_meta_out}"
      COMMAND ${Python3_EXECUTABLE}
              "${_gen_meta}"
              "${_hdr_abs}"
              "${_payload_name}"
              "${_meta_out}"
              --depfile "${_depfile}"
              --
              -x ${_clang_lang}
              ${_swig_flags}
      DEPENDS "${_hdr_abs}" "${_gen_meta}"
      DEPFILE "${_depfile}"
      COMMENT "Generating metadata JSON for ${_payload_name}"
      VERBATIM
    )

    # Generate the per-payload equality traits header included by the SWIG
    # template. Basilisk's generator includes payload headers below
    # "architecture/${_eq_payload_search_dir}", so create a forwarding include
    # tree in autoSource that points back to the extension's real payload header.
    set(_eq_payload_search_dir "bskSdkExtensionPayloads")
    file(TO_CMAKE_PATH "${_hdr_abs}" _hdr_include)
    set(_eq_forward_dir "${_auto_root}/architecture/${_eq_payload_search_dir}")
    set(_eq_forward_hdr "${_eq_forward_dir}/${_payload_name}.h")
    file(MAKE_DIRECTORY "${_eq_forward_dir}")
    file(WRITE "${_eq_forward_hdr}"
      "#pragma once\n"
      "#include \"${_hdr_include}\"\n"
    )

    set(_eq_out "${_auto_root}/${_payload_name}_equality.h")
    add_custom_command(
      OUTPUT "${_eq_out}"
      COMMAND ${Python3_EXECUTABLE}
              "${_gen_eq}"
              "${_eq_out}" "${_meta_out}" "${_payload_name}" "${_eq_payload_search_dir}"
      DEPENDS "${_meta_out}" "${_gen_eq}" "${_eq_forward_hdr}"
      WORKING_DIRECTORY "${_msg_autosrc}"
      COMMENT "Generating payload equality header for ${_payload_name}"
      VERBATIM
    )

    # Generate the .i interface file from the JSON
    set(_i_out "${_auto_root}/${_payload_name}.i")
    add_custom_command(
      OUTPUT "${_i_out}"
      COMMAND ${Python3_EXECUTABLE}
              "${_gen_swig}"
              "${_i_out}" "${_hdr_abs}" "${_payload_name}" "${_hdr_dir}"
              "${_gen_c}"
              "${_meta_out}" 0
      DEPENDS "${_hdr_abs}" "${_meta_out}" "${_eq_out}" "${_gen_swig}" "${_msg_autosrc}/msgInterfacePy.i.in"
      WORKING_DIRECTORY "${_msg_autosrc}"
      COMMENT "Generating SWIG interface for ${_payload_name}"
      VERBATIM
    )

    # cmake's UseSWIG scans .i files for %include dependencies at generate time,
    # so the file must exist on disk before swig_add_library runs. Bootstrap both
    # the JSON and the .i once at configure time. add_custom_command handles all
    # subsequent incremental rebuilds.
    if(NOT EXISTS "${_meta_out}")
      execute_process(
        COMMAND ${Python3_EXECUTABLE}
                "${_gen_meta}"
                "${_hdr_abs}"
                "${_payload_name}"
                "${_meta_out}"
                --
                -x ${_clang_lang}
                ${_swig_flags}
        RESULT_VARIABLE _gen_rc
        ERROR_VARIABLE  _gen_err
      )
      if(NOT _gen_rc EQUAL 0)
        message(FATAL_ERROR
          "generatePayloadMetaJson.py failed for ${_payload_name}:\n${_gen_err}")
      endif()
    endif()

    if(NOT EXISTS "${_eq_out}")
      execute_process(
        COMMAND ${Python3_EXECUTABLE}
                "${_gen_eq}"
                "${_eq_out}" "${_meta_out}" "${_payload_name}" "${_eq_payload_search_dir}"
        WORKING_DIRECTORY "${_msg_autosrc}"
        RESULT_VARIABLE _gen_rc
        ERROR_VARIABLE  _gen_err
      )
      if(NOT _gen_rc EQUAL 0)
        message(FATAL_ERROR
          "generatePayloadEqualityHeader.py failed for ${_payload_name}:\n${_gen_err}")
      endif()
    endif()

    if(NOT EXISTS "${_i_out}")
      execute_process(
        COMMAND ${Python3_EXECUTABLE}
                "${_gen_swig}"
                "${_i_out}" "${_hdr_abs}" "${_payload_name}" "${_hdr_dir}"
                "${_gen_c}"
                "${_meta_out}" 0
        WORKING_DIRECTORY "${_msg_autosrc}"
        RESULT_VARIABLE _gen_rc
        ERROR_VARIABLE  _gen_err
      )
      if(NOT _gen_rc EQUAL 0)
        message(FATAL_ERROR
          "generateSWIGModules.py failed for ${_payload_name}:\n${_gen_err}")
      endif()
    endif()

    # Build the SWIG module
    set_source_files_properties("${_i_out}" PROPERTIES GENERATED TRUE)
    set_property(SOURCE "${_i_out}" PROPERTY CPLUSPLUS ON)
    set_property(SOURCE "${_i_out}" PROPERTY USE_TARGET_INCLUDE_DIRECTORIES TRUE)
    set_property(SOURCE "${_i_out}" PROPERTY SWIG_FLAGS ${_swig_flags})

    swig_add_library(
      ${_payload_name}
      LANGUAGE python
      TYPE MODULE
      SOURCES "${_i_out}"
      OUTPUT_DIR "${BSK_OUTPUT_DIR}"
      OUTFILE_DIR "${_auto_root}"
    )

    _bsk_configure_swig_target(
      ${_payload_name} "${BSK_OUTPUT_DIR}" "${BSK_TARGET_LINK_LIBS}"
      "${BSK_INCLUDE_DIRS};${_hdr_dir};${_auto_root}"
    )

    list(APPEND _generated_targets ${_payload_name})
  endforeach()

  # Generate __init__.py that re-exports all message payloads. Importing this
  # package also registers the SWIG proxy classes for the generated Message<T>
  # and Recorder<T> specializations, plus payload dtypes used by NumbaModel.
  # Extension package __init__.py files should therefore import their generated
  # messaging package before importing module wrappers.
  file(MAKE_DIRECTORY "${BSK_OUTPUT_DIR}")
  set(_init_file "${BSK_OUTPUT_DIR}/__init__.py")
  file(WRITE "${_init_file}"
    "\"\"\"Generated Basilisk message bindings for this extension.\n\n"
    "Importing this package registers custom Message<T> and Recorder<T> SWIG\n"
    "proxy classes, including recorder() methods and NumbaModel payload dtypes.\n"
    "\"\"\"\n\n"
    "from Basilisk.architecture import messaging as _bsk_messaging\n\n\n"
    "def _register_numba_payload(payload_class):\n"
    "    \"\"\"Expose an extension payload dtype to Basilisk NumbaModel.\"\"\"\n"
    "    payload_name = payload_class.__name__\n"
    "    existing = getattr(_bsk_messaging, payload_name, None)\n"
    "    if existing is not None and existing is not payload_class:\n"
    "        raise ImportError(\n"
    "            f\"Cannot register extension payload {payload_name!r} for NumbaModel: \"\n"
    "            \"Basilisk.architecture.messaging already exposes a different \"\n"
    "            \"payload class with that name. Rename the extension payload to \"\n"
    "            \"avoid ambiguous dtype resolution.\"\n"
    "        )\n"
    "    setattr(_bsk_messaging, payload_name, payload_class)\n\n"
  )
  foreach(_hdr IN LISTS BSK_MSG_HEADERS)
    get_filename_component(_payload_name "${_hdr}" NAME_WE)
    file(APPEND "${_init_file}"
      "from .${_payload_name} import *\n"
      "_register_numba_payload(${_payload_name})\n"
    )
  endforeach()

  if(BSK_OUT_VAR)
    set(${BSK_OUT_VAR} "${_generated_targets}" PARENT_SCOPE)
  endif()
endfunction()
