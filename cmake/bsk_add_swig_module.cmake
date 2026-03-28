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

# Shared helpers
# Collect the -I flags that every SWIG invocation needs.
function(_bsk_collect_swig_flags out_var)
  set(_flags
    "-I${BSK_SDK_SWIG_DIR}"
    "-I${BSK_SDK_SWIG_DIR}/architecture"
    "-I${BSK_SDK_SWIG_DIR}/architecture/_GeneralModuleFiles"

    "-I${BSK_SDK_INCLUDE_DIR}"
    "-I${BSK_SDK_INCLUDE_DIR}/Basilisk"
    "-I${BSK_SDK_INCLUDE_DIR}/Basilisk/architecture"
    "-I${BSK_SDK_INCLUDE_DIR}/Basilisk/architecture/_GeneralModuleFiles"

    "-I${Python3_INCLUDE_DIRS}"
  )

  if(DEFINED BSK_SDK_COMPAT_INCLUDE_DIR AND EXISTS "${BSK_SDK_COMPAT_INCLUDE_DIR}")
    list(APPEND _flags "-I${BSK_SDK_COMPAT_INCLUDE_DIR}")
  endif()

  if(Python3_NumPy_INCLUDE_DIRS)
    list(APPEND _flags "-I${Python3_NumPy_INCLUDE_DIRS}")
  endif()

  foreach(_dir IN LISTS BSK_SWIG_INCLUDE_DIRS)
    list(APPEND _flags "-I${_dir}")
  endforeach()

  foreach(_dir IN LISTS BSK_INCLUDE_DIRS)
    list(APPEND _flags "-I${_dir}")
  endforeach()

  set(${out_var} "${_flags}" PARENT_SCOPE)
endfunction()

# Locate the installed Basilisk package and return its runtime libraries.
function(_bsk_resolve_basilisk_libs out_var)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)

  execute_process(
    COMMAND "${Python3_EXECUTABLE}" -c
      "import Basilisk, pathlib; print(pathlib.Path(Basilisk.__file__).resolve().parent, end='')"
    OUTPUT_VARIABLE _bsk_root
    RESULT_VARIABLE _bsk_res
  )
  if(NOT _bsk_res EQUAL 0 OR NOT EXISTS "${_bsk_root}")
    message(FATAL_ERROR "Failed to locate installed Basilisk package (needed to link runtime libs).")
  endif()

  set(_lib_dir "${_bsk_root}")
  set(_names architectureLib ArchitectureUtilities cMsgCInterface)
  set(_libs "")
  foreach(_name IN LISTS _names)
    find_library(_lib NAMES ${_name} PATHS "${_lib_dir}" NO_DEFAULT_PATH)
    if(NOT _lib)
      message(FATAL_ERROR "Basilisk library '${_name}' not found under ${_lib_dir}")
    endif()
    list(APPEND _libs "${_lib}")
  endforeach()

  set(${out_var} "${_libs}" PARENT_SCOPE)
endfunction()

# Run find_package for Python, SWIG, and Eigen3.
macro(_bsk_find_build_deps)
  find_package(Python3 QUIET COMPONENTS Interpreter)
  _bsk_setup_pip_swig("${Python3_EXECUTABLE}")
  find_package(SWIG REQUIRED COMPONENTS python)
  include(${SWIG_USE_FILE})
  find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module NumPy)
  find_package(Eigen3 CONFIG REQUIRED)
endmacro()

# Resolve link libraries: prefer the SDK's bsk::arch_min target, fall back to
# the installed Basilisk runtime libs.
function(_bsk_resolve_link_libs out_var)
  if(TARGET bsk::arch_min)
    set(${out_var} "bsk::arch_min" PARENT_SCOPE)
  else()
    _bsk_resolve_basilisk_libs(_libs)
    set(${out_var} "${_libs}" PARENT_SCOPE)
  endif()
endfunction()

# Apply the standard include directories, link libraries, PIC flag, and
# MSVC multi-config output directory overrides to a SWIG module target.
function(_bsk_configure_swig_target target_name output_dir link_libs extra_include_dirs)
  target_include_directories(${target_name} PRIVATE
    ${extra_include_dirs}
    "${BSK_SDK_INCLUDE_DIR}"
    "${BSK_SDK_INCLUDE_DIR}/Basilisk"
    "${BSK_SDK_INCLUDE_DIR}/Basilisk/architecture"
    "${BSK_SDK_INCLUDE_DIR}/Basilisk/architecture/_GeneralModuleFiles"
    $<$<BOOL:${BSK_SDK_COMPAT_INCLUDE_DIR}>:${BSK_SDK_COMPAT_INCLUDE_DIR}>
    ${Python3_INCLUDE_DIRS}
    ${Python3_NumPy_INCLUDE_DIRS}
  )

  target_link_libraries(${target_name} PRIVATE
    Python3::Module
    Eigen3::Eigen
    ${link_libs}
  )

  set_target_properties(${target_name} PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${output_dir}"
    RUNTIME_OUTPUT_DIRECTORY "${output_dir}"
  )
  foreach(_cfg RELEASE DEBUG RELWITHDEBINFO MINSIZEREL)
    set_target_properties(${target_name} PROPERTIES
      LIBRARY_OUTPUT_DIRECTORY_${_cfg} "${output_dir}"
      RUNTIME_OUTPUT_DIRECTORY_${_cfg} "${output_dir}"
    )
  endforeach()
endfunction()

# Pip-installed SWIG detection and runtime-version validation
function(_bsk_setup_pip_swig python_exe)
  if(NOT python_exe)
    return()
  endif()

  # Single Python call to find both the swig binary and its lib directory.
  execute_process(
    COMMAND "${python_exe}" -c
      "import sys, pathlib, os\n\
exe_name = 'swig.exe' if os.name == 'nt' else 'swig'\n\
exe_path = lib_path = ''\n\
for p in sys.path:\n\
    base = pathlib.Path(p) / 'swig' / 'data'\n\
    candidate = base / 'bin' / exe_name\n\
    if candidate.exists():\n\
        exe_path = str(candidate)\n\
        share = base / 'share' / 'swig'\n\
        if share.exists():\n\
            dirs = sorted(d for d in share.iterdir() if d.is_dir())\n\
            if dirs:\n\
                lib_path = dirs[-1].as_posix()\n\
        break\n\
print(f'{exe_path};{lib_path}', end='')"
    OUTPUT_VARIABLE _pip_swig_result
    RESULT_VARIABLE _pip_swig_rc
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )

  list(LENGTH _pip_swig_result _pip_swig_len)
  if(_pip_swig_rc EQUAL 0 AND _pip_swig_len EQUAL 2)
    list(GET _pip_swig_result 0 _pip_swig_exe)
    list(GET _pip_swig_result 1 _pip_swig_lib)
  else()
    return()
  endif()

  if(NOT EXISTS "${_pip_swig_exe}" OR NOT EXISTS "${_pip_swig_lib}")
    return()
  endif()

  execute_process(
    COMMAND "${_pip_swig_exe}" -version
    RESULT_VARIABLE _pip_swig_works
    OUTPUT_QUIET ERROR_QUIET
  )
  if(NOT _pip_swig_works EQUAL 0)
    return()
  endif()
  set(SWIG_DIR "${_pip_swig_lib}" CACHE PATH "SWIG lib from pip" FORCE)
  set(ENV{SWIG_LIB} "${_pip_swig_lib}")

  # Create a thin wrapper that exports SWIG_LIB for ninja subprocesses.
  if(WIN32)
    set(_wrapper "${CMAKE_BINARY_DIR}/bsk_swig_wrapper.bat")
    file(WRITE "${_wrapper}"
      "@echo off\r\n"
      "set \"SWIG_LIB=${_pip_swig_lib}\"\r\n"
      "\"${_pip_swig_exe}\" %*\r\n"
    )
  else()
    set(_wrapper "${CMAKE_BINARY_DIR}/bsk_swig_wrapper.sh")
    file(WRITE "${_wrapper}"
      "#!/bin/sh\n"
      "export SWIG_LIB=\"${_pip_swig_lib}\"\n"
      "exec \"${_pip_swig_exe}\" \"$@\"\n"
    )
    execute_process(COMMAND chmod +x "${_wrapper}")
  endif()

  set(SWIG_EXECUTABLE "${_wrapper}" CACHE FILEPATH "SWIG wrapper from pip" FORCE)
  message(STATUS "bsk-sdk: using pip SWIG ${_pip_swig_exe} (lib: ${_pip_swig_lib})")

  # Validate SWIG runtime version matches Basilisk's.
  file(STRINGS "${_pip_swig_lib}/swigrun.swg" _swigrun_lines
       REGEX "SWIG_RUNTIME_VERSION")
  set(_plugin_rt "")
  foreach(_line IN LISTS _swigrun_lines)
    if(_line MATCHES "#define SWIG_RUNTIME_VERSION \"([0-9]+)\"")
      set(_plugin_rt "${CMAKE_MATCH_1}")
    endif()
  endforeach()

  execute_process(
    COMMAND "${python_exe}" -c
      "import sys\n\
try:\n\
    import Basilisk.architecture.cSysModel\n\
    keys = [k for k in sys.modules if k.startswith('swig_runtime_data')]\n\
    print(keys[0].replace('swig_runtime_data', '') if keys else '', end='')\n\
except ImportError:\n\
    print('', end='')"
    OUTPUT_VARIABLE _bsk_rt
    RESULT_VARIABLE _bsk_rt_rc
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )

  if(_plugin_rt AND _bsk_rt AND NOT _plugin_rt STREQUAL _bsk_rt)
    message(FATAL_ERROR
      "SWIG runtime version mismatch!\n"
      "  bsk was compiled with SWIG_RUNTIME_VERSION \"${_bsk_rt}\" "
      "(capsule: swig_runtime_data${_bsk_rt})\n"
      "  pip swig ${_pip_swig_exe} uses SWIG_RUNTIME_VERSION \"${_plugin_rt}\" "
      "(capsule: swig_runtime_data${_plugin_rt})\n\n"
      "Plugins compiled with this SWIG version cannot exchange objects with "
      "Basilisk across module boundaries.\n"
      "Install a SWIG version that matches bsk's runtime epoch.\n"
      "  bsk-sdk declares: swig>=4.2.1,<=4.3.1  (runtime version 4, matching bsk)\n"
      "  Reinstall with:  pip install \"swig>=4.2.1,<=4.3.1\""
    )
  endif()
endfunction()

function(bsk_add_swig_module)
  set(oneValueArgs TARGET INTERFACE OUTPUT_DIR)
  set(multiValueArgs SOURCES INCLUDE_DIRS SWIG_INCLUDE_DIRS LINK_LIBS DEPENDS)
  cmake_parse_arguments(BSK "" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

  if(NOT BSK_TARGET OR NOT BSK_INTERFACE)
    message(FATAL_ERROR "bsk_add_swig_module requires TARGET and INTERFACE (.i file)")
  endif()

  if(NOT BSK_OUTPUT_DIR)
    set(BSK_OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}")
  endif()

  _bsk_find_build_deps()

  if(NOT BSK_LINK_LIBS)
    _bsk_resolve_link_libs(BSK_LINK_LIBS)
  endif()

  _bsk_collect_swig_flags(_swig_flags)

  set_property(SOURCE "${BSK_INTERFACE}" PROPERTY CPLUSPLUS ON)
  set_property(SOURCE "${BSK_INTERFACE}" PROPERTY USE_TARGET_INCLUDE_DIRECTORIES TRUE)
  set_property(SOURCE "${BSK_INTERFACE}" PROPERTY SWIG_FLAGS ${_swig_flags})

  set(_wrap_dir "${CMAKE_CURRENT_BINARY_DIR}/swig/${BSK_TARGET}")
  file(MAKE_DIRECTORY "${_wrap_dir}")

  swig_add_library(
    ${BSK_TARGET}
    LANGUAGE python
    TYPE MODULE
    SOURCES "${BSK_INTERFACE}" ${BSK_SOURCES}
    OUTPUT_DIR "${BSK_OUTPUT_DIR}"
    OUTFILE_DIR "${_wrap_dir}"
  )

  _bsk_configure_swig_target(
    ${BSK_TARGET} "${BSK_OUTPUT_DIR}" "${BSK_LINK_LIBS}" "${BSK_INCLUDE_DIRS}"
  )

  if(BSK_DEPENDS)
    add_dependencies(${BSK_TARGET} ${BSK_DEPENDS})
  endif()
endfunction()
