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

# Locate the msgAutoSource directory that ships generateSWIGModules.py.
function(_bsk_resolve_msg_autosource_dir out_var)
  if(DEFINED BSK_SDK_MSG_AUTOSOURCE_DIR
      AND EXISTS "${BSK_SDK_MSG_AUTOSOURCE_DIR}/generateSWIGModules.py")
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
    if(EXISTS "${_cand}/generateSWIGModules.py")
      set(${out_var} "${_cand}" PARENT_SCOPE)
      return()
    endif()
  endforeach()

  string(JOIN "\n  " _cand_list ${_candidates})
  message(FATAL_ERROR
    "bsk-sdk message generator not found.\n\n"
    "Looked for generateSWIGModules.py under:\n"
    "  ${_cand_list}\n\n"
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

  if(NOT BSK_TARGET_LINK_LIBS)
    _bsk_resolve_link_libs(BSK_TARGET_LINK_LIBS)
  endif()

  _bsk_collect_swig_flags(_swig_flags)
  _bsk_resolve_msg_autosource_dir(_msg_autosrc)

  set(_gen_swig "${_msg_autosrc}/generateSWIGModules.py")
  set(_gen_meta "${_msg_autosrc}/generatePayloadMetaJson.py")
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

    # Generate the .i interface file from the JSON
    set(_i_out "${_auto_root}/${_payload_name}.i")
    add_custom_command(
      OUTPUT "${_i_out}"
      COMMAND ${Python3_EXECUTABLE}
              "${_gen_swig}"
              "${_i_out}" "${_hdr_abs}" "${_payload_name}" "${_hdr_dir}"
              "${_gen_c}"
              "${_meta_out}" 0
      DEPENDS "${_hdr_abs}" "${_meta_out}" "${_gen_swig}" "${_msg_autosrc}/msgInterfacePy.i.in"
      WORKING_DIRECTORY "${_msg_autosrc}"
      COMMENT "Generating SWIG interface for ${_payload_name}"
      VERBATIM
    )

    # Build the SWIG module
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
      "${BSK_INCLUDE_DIRS};${_hdr_dir}"
    )

    list(APPEND _generated_targets ${_payload_name})
  endforeach()

  # Generate __init__.py that re-exports all message payloads
  file(MAKE_DIRECTORY "${BSK_OUTPUT_DIR}")
  set(_init_file "${BSK_OUTPUT_DIR}/__init__.py")
  file(WRITE "${_init_file}" "")
  foreach(_hdr IN LISTS BSK_MSG_HEADERS)
    get_filename_component(_payload_name "${_hdr}" NAME_WE)
    file(APPEND "${_init_file}" "from .${_payload_name} import *\n")
  endforeach()

  if(BSK_OUT_VAR)
    set(${BSK_OUT_VAR} "${_generated_targets}" PARENT_SCOPE)
  endif()
endfunction()
