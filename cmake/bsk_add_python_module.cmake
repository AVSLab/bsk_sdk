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
include(CMakeParseArguments)

# Copy one pure-Python Basilisk module into an extension package.  This mirrors
# Basilisk's configure-time handling for Python modules under fswAlgorithms and
# simulation.  configure_file() also makes CMake reconfigure when the source
# changes, so rebuilt wheels receive the updated module.
function(bsk_add_python_module)
  set(oneValueArgs SOURCE OUTPUT_DIR OUT_VAR)
  cmake_parse_arguments(BSK "" "${oneValueArgs}" "" ${ARGN})

  if(BSK_UNPARSED_ARGUMENTS)
    message(FATAL_ERROR
      "bsk_add_python_module received unexpected arguments: ${BSK_UNPARSED_ARGUMENTS}"
    )
  endif()

  if(NOT BSK_SOURCE)
    message(FATAL_ERROR "bsk_add_python_module requires SOURCE")
  endif()

  if(NOT BSK_OUTPUT_DIR)
    set(BSK_OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}")
  endif()

  get_filename_component(
    _bsk_python_source "${BSK_SOURCE}" ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}"
  )
  if(NOT EXISTS "${_bsk_python_source}" OR IS_DIRECTORY "${_bsk_python_source}")
    message(FATAL_ERROR
      "bsk_add_python_module SOURCE is not a file: ${_bsk_python_source}"
    )
  endif()

  get_filename_component(_bsk_python_extension "${_bsk_python_source}" EXT)
  if(NOT _bsk_python_extension STREQUAL ".py")
    message(FATAL_ERROR
      "bsk_add_python_module SOURCE must be a .py file: ${_bsk_python_source}"
    )
  endif()

  get_filename_component(_bsk_python_filename "${_bsk_python_source}" NAME)
  file(MAKE_DIRECTORY "${BSK_OUTPUT_DIR}")
  set(_bsk_python_output "${BSK_OUTPUT_DIR}/${_bsk_python_filename}")
  configure_file("${_bsk_python_source}" "${_bsk_python_output}" COPYONLY)

  if(BSK_OUT_VAR)
    set(${BSK_OUT_VAR} "${_bsk_python_output}" PARENT_SCOPE)
  endif()
endfunction()
