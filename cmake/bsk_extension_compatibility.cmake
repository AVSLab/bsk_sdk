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

function(_bsk_sdk_basilisk_version_guidance sdk_version out_var)
  string(TOLOWER "${sdk_version}" _version)
  if(_version MATCHES "(a|b|alpha|beta)[0-9]+$")
    string(CONCAT _guidance
      "Alpha and beta builds must use matching Basilisk and bsk-sdk sources "
      "or wheels. Install or build the intended Basilisk prerelease, or "
      "resynchronize bsk-sdk from that same Basilisk checkout, then try again.")
  elseif(_version MATCHES "rc[0-9]+$")
    string(CONCAT _guidance
      "Install the matching Basilisk release candidate from TestPyPI:\n"
      "  python3 -m pip install --pre --index-url "
      "https://test.pypi.org/simple/ --extra-index-url "
      "https://pypi.org/simple/ \"bsk[all]==${sdk_version}\"\n"
      "Alternatively, resynchronize bsk-sdk from the matching Basilisk release.")
  else()
    string(CONCAT _guidance
      "Install the matching Basilisk release from PyPI:\n"
      "  python3 -m pip install \"bsk[all]==${sdk_version}\"\n"
      "Alternatively, resynchronize bsk-sdk from the matching Basilisk release.")
  endif()
  set("${out_var}" "${_guidance}" PARENT_SCOPE)
endfunction()

function(_bsk_sdk_require_exact_basilisk_version installed_version sdk_version)
  if("${installed_version}" STREQUAL "${sdk_version}")
    return()
  endif()

  _bsk_sdk_basilisk_version_guidance("${sdk_version}" _guidance)
  message(FATAL_ERROR
    "Basilisk version mismatch!\n"
    "  bsk-sdk was synced from Basilisk ${sdk_version}\n"
    "  Installed Basilisk is ${installed_version}\n\n"
    "Extensions compiled against mismatched headers will have ABI incompatibilities.\n"
    "${_guidance}"
  )
endfunction()

function(bsk_add_extension_compatibility_guard)
  set(_one EXTENSION_NAME OUTPUT_DIR)
  cmake_parse_arguments(BSK "" "${_one}" "" ${ARGN})
  if(NOT BSK_EXTENSION_NAME OR NOT BSK_OUTPUT_DIR)
    message(FATAL_ERROR
      "bsk_add_extension_compatibility_guard requires EXTENSION_NAME and OUTPUT_DIR")
  endif()
  if(NOT BSK_EXTENSION_NAME MATCHES "^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    message(FATAL_ERROR
      "EXTENSION_NAME must contain only letters, digits, periods, underscores, and hyphens")
  endif()
  if(NOT DEFINED BSK_SDK_BSK_VERSION OR BSK_SDK_BSK_VERSION STREQUAL "")
    message(FATAL_ERROR "bsk-sdk did not provide its synchronized Basilisk version")
  endif()

  set(_abi_header
      "${BSK_SDK_INCLUDE_DIR}/Basilisk/architecture/utilities/bskAbiDescriptor.h")
  if(NOT EXISTS "${_abi_header}")
    message(FATAL_ERROR "Basilisk ABI descriptor header not found: ${_abi_header}")
  endif()
  file(STRINGS "${_abi_header}" _abi_definition
       REGEX "^#define[ \t]+BSK_EXTENSION_ABI_VERSION[ \t]+[0-9]+")
  list(LENGTH _abi_definition _abi_definition_count)
  if(NOT _abi_definition_count EQUAL 1)
    message(FATAL_ERROR
      "Expected exactly one BSK_EXTENSION_ABI_VERSION definition in ${_abi_header}")
  endif()
  string(REGEX MATCH "[0-9]+$" BSK_EXTENSION_ABI_VERSION "${_abi_definition}")

  set(BSK_EXTENSION_COMPATIBILITY_NAME "${BSK_EXTENSION_NAME}")
  set(BSK_EXTENSION_COMPATIBILITY_VERSION "${BSK_SDK_BSK_VERSION}")
  file(MAKE_DIRECTORY "${BSK_OUTPUT_DIR}")
  configure_file(
    "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/bsk_extension_compatibility.py.in"
    "${BSK_OUTPUT_DIR}/_bsk_compatibility.py"
    @ONLY
  )
endfunction()
