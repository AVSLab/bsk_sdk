include_guard(GLOBAL)
include(CMakeParseArguments)

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

# Resolve the pip-installed swig from the active Python interpreter.
# Creates a thin wrapper script that exports SWIG_LIB before exec'ing the
# real binary, then sets SWIG_EXECUTABLE to the wrapper and SWIG_DIR for
# FindSWIG. This ensures every swig invocation by ninja gets the right lib
# path without any manual configuration from the plugin author.
function(_bsk_setup_pip_swig python_exe)
  if(NOT python_exe)
    return()
  endif()

  execute_process(
    COMMAND "${python_exe}" -c
      "import swig, os, pathlib; \
exe = 'swig.exe' if os.name == 'nt' else 'swig'; \
print(pathlib.Path(swig.BIN_DIR, exe).as_posix(), end='')"
    OUTPUT_VARIABLE _pip_swig_exe
    RESULT_VARIABLE _pip_swig_rc
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )

  execute_process(
    COMMAND "${python_exe}" -c
      "import swig, pathlib; \
print(pathlib.Path(swig.SWIG_SHARE_DIR, swig.__version__).as_posix(), end='')"
    OUTPUT_VARIABLE _pip_swig_lib
    RESULT_VARIABLE _pip_swig_lib_rc
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )

  if(_pip_swig_rc EQUAL 0 AND EXISTS "${_pip_swig_exe}"
      AND _pip_swig_lib_rc EQUAL 0 AND EXISTS "${_pip_swig_lib}")
    # SWIG_DIR is needed by FindSWIG during cmake configure to locate swig.swg.
    set(SWIG_DIR "${_pip_swig_lib}" CACHE PATH "SWIG lib from pip" FORCE)

    # set(ENV{SWIG_LIB} ...) only affects the cmake configure process — ninja
    # subprocesses that invoke swig during the build don't inherit it.  Wrap
    # the real swig binary in a thin script that exports SWIG_LIB first, then
    # point SWIG_EXECUTABLE at the wrapper so every swig invocation gets it.
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

    # Runtime-version guard: SWIG_RUNTIME_VERSION in swigrun.swg determines
    # the sys.modules capsule name (swig_runtime_dataX).  Modules compiled with
    # different values cannot share the type table, so cross-module type casts
    # (e.g. passing a plugin object to Basilisk's AddModelToTask) silently fail.
    # Detect the mismatch here and abort with a clear message.
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
        "  bsk-sdk declares: swig>=4.0,<4.4  (runtime version 4, matching bsk 4.3.1)\n"
        "  Reinstall with:  pip install \"swig>=4.0,<4.4\""
      )
    endif()
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

  find_package(Python3 QUIET COMPONENTS Interpreter)
  _bsk_setup_pip_swig("${Python3_EXECUTABLE}")

  find_package(SWIG REQUIRED COMPONENTS python)
  include(${SWIG_USE_FILE})

  find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module NumPy)
  find_package(Eigen3 CONFIG REQUIRED)

  if(NOT BSK_LINK_LIBS)
    if(TARGET bsk::arch_min)
      set(BSK_LINK_LIBS "bsk::arch_min")
    else()
      _bsk_resolve_basilisk_libs(_bsk_libs)
      set(BSK_LINK_LIBS "${_bsk_libs}")
    endif()
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

  target_include_directories(${BSK_TARGET} PRIVATE
    ${BSK_INCLUDE_DIRS}
    "${BSK_SDK_INCLUDE_DIR}"
    "${BSK_SDK_INCLUDE_DIR}/Basilisk"
    "${BSK_SDK_INCLUDE_DIR}/Basilisk/architecture"
    "${BSK_SDK_INCLUDE_DIR}/Basilisk/architecture/_GeneralModuleFiles"
    $<$<BOOL:${BSK_SDK_COMPAT_INCLUDE_DIR}>:${BSK_SDK_COMPAT_INCLUDE_DIR}>
    ${Python3_INCLUDE_DIRS}
    ${Python3_NumPy_INCLUDE_DIRS}
  )

  target_link_libraries(${BSK_TARGET} PRIVATE
    Python3::Module
    Eigen3::Eigen
    ${BSK_LINK_LIBS}
  )

  if(BSK_DEPENDS)
    add_dependencies(${BSK_TARGET} ${BSK_DEPENDS})
  endif()

  set_target_properties(${BSK_TARGET} PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${BSK_OUTPUT_DIR}"
    RUNTIME_OUTPUT_DIRECTORY "${BSK_OUTPUT_DIR}"
  )
  # On MSVC multi-config generators the per-config variants take precedence and
  # default to appending Release/Debug/... subdirectories. Override them so the
  # output always lands in BSK_OUTPUT_DIR regardless of generator.
  foreach(_cfg RELEASE DEBUG RELWITHDEBINFO MINSIZEREL)
    set_target_properties(${BSK_TARGET} PROPERTIES
      LIBRARY_OUTPUT_DIRECTORY_${_cfg} "${BSK_OUTPUT_DIR}"
      RUNTIME_OUTPUT_DIRECTORY_${_cfg} "${BSK_OUTPUT_DIR}"
    )
  endforeach()
endfunction()
