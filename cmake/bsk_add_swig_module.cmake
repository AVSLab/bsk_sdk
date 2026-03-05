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

function(_bsk_find_working_swig out_var)
  set(_swig_candidates "")

  if(DEFINED SWIG_EXECUTABLE AND SWIG_EXECUTABLE)
    list(APPEND _swig_candidates "${SWIG_EXECUTABLE}")
  endif()

  find_program(_swig_on_path NAMES swig)
  if(_swig_on_path)
    list(APPEND _swig_candidates "${_swig_on_path}")
  endif()

  execute_process(
    COMMAND brew --prefix swig
    OUTPUT_VARIABLE _brew_swig_prefix
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
    RESULT_VARIABLE _brew_swig_res
  )
  if(_brew_swig_res EQUAL 0 AND EXISTS "${_brew_swig_prefix}/bin/swig")
    list(APPEND _swig_candidates "${_brew_swig_prefix}/bin/swig")
  endif()

  file(GLOB _cellar_swigs "/opt/homebrew/Cellar/swig/*/bin/swig")
  list(SORT _cellar_swigs ORDER DESCENDING)
  if(_cellar_swigs)
    list(APPEND _swig_candidates ${_cellar_swigs})
  endif()

  list(REMOVE_DUPLICATES _swig_candidates)

  foreach(_cand IN LISTS _swig_candidates)
    if(NOT EXISTS "${_cand}")
      continue()
    endif()

    execute_process(
      COMMAND "${_cand}" -version
      OUTPUT_VARIABLE _swig_stdout
      ERROR_VARIABLE _swig_stderr
      OUTPUT_STRIP_TRAILING_WHITESPACE
      ERROR_STRIP_TRAILING_WHITESPACE
      RESULT_VARIABLE _swig_res
    )

    if(_swig_res EQUAL 0)
      string(CONCAT _swig_text "${_swig_stdout}" "\n" "${_swig_stderr}")
      if(_swig_text MATCHES "SWIG Version")
        set(${out_var} "${_cand}" PARENT_SCOPE)
        return()
      endif()
    endif()
  endforeach()

  set(${out_var} "" PARENT_SCOPE)
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

  _bsk_find_working_swig(_bsk_working_swig)
  if(_bsk_working_swig)
    set(SWIG_EXECUTABLE "${_bsk_working_swig}" CACHE FILEPATH "Working SWIG executable" FORCE)
  endif()

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
