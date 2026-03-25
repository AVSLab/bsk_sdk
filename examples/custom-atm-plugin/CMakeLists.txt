cmake_minimum_required(VERSION 3.18)
project(bsk_plugin_exponential_atmosphere LANGUAGES C CXX)

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module NumPy)

# Locate bsk-sdk's CMake config dir from the active Python env
execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c "import bsk_sdk; print(bsk_sdk.cmake_config_dir(), end='')"
  OUTPUT_VARIABLE bsk_sdk_dir
  RESULT_VARIABLE rc
)
if(NOT rc EQUAL 0 OR bsk_sdk_dir STREQUAL "")
  message(FATAL_ERROR "bsk-sdk not found (is it installed in this Python environment?)")
endif()
file(TO_CMAKE_PATH "${bsk_sdk_dir}" bsk_sdk_dir)

set(bsk-sdk_DIR "${bsk_sdk_dir}")
find_package(bsk-sdk CONFIG REQUIRED)

execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c "import bsk_sdk; print(bsk_sdk.package_root(), end='')"
  OUTPUT_VARIABLE bsk_sdk_pkg_dir
  RESULT_VARIABLE bsk_sdk_pkg_rc
)
if(NOT bsk_sdk_pkg_rc EQUAL 0 OR bsk_sdk_pkg_dir STREQUAL "")
  message(FATAL_ERROR "Could not resolve bsk_sdk package_root()")
endif()
file(TO_CMAKE_PATH "${bsk_sdk_pkg_dir}" bsk_sdk_pkg_dir)

# Resolve Basilisk runtime libraries from the active Python environment.
# The plugin must link against the same Basilisk libs that back
# Basilisk.utilities.SimulationBaseClass to keep SysModel C++ type identity
# consistent across module boundaries.
execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c "import Basilisk, pathlib; print(pathlib.Path(Basilisk.__file__).resolve().parent, end='')"
  OUTPUT_VARIABLE basilisk_pkg_dir
  RESULT_VARIABLE basilisk_rc
)
if(NOT basilisk_rc EQUAL 0 OR basilisk_pkg_dir STREQUAL "")
  message(FATAL_ERROR "Basilisk package not found in this Python environment")
endif()
file(TO_CMAKE_PATH "${basilisk_pkg_dir}" basilisk_pkg_dir)

set(_basilisk_lib_names architectureLib ArchitectureUtilities cMsgCInterface)
set(BASILISK_RUNTIME_LIBS "")
foreach(_libname IN LISTS _basilisk_lib_names)
  find_library(_libpath NAMES ${_libname} PATHS "${basilisk_pkg_dir}" NO_DEFAULT_PATH)
  if(NOT _libpath)
    message(FATAL_ERROR "Basilisk runtime library '${_libname}' not found under ${basilisk_pkg_dir}")
  endif()
  list(APPEND BASILISK_RUNTIME_LIBS "${_libpath}")
endforeach()

# Where scikit-build-core wants wheel outputs
set(PLUGIN_PKG_DIR "${SKBUILD_PLATLIB_DIR}/custom_atm")

# Plugin sources
file(GLOB PLUGIN_SOURCES CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/src/*.c"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cc"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cxx"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp"
)

# AtmosphereBase implementation is required at link/load time for the custom
# model subclass. Prefer the SDK-shipped runtime source to avoid depending on
# repository-local external/basilisk checkout structure in CI.
set(_atm_base_impl "${bsk_sdk_pkg_dir}/runtime_min/atmosphereBase.cpp")
if(NOT EXISTS "${_atm_base_impl}")
  set(_atm_base_impl
    "${CMAKE_CURRENT_SOURCE_DIR}/../../src/bsk_sdk/runtime_min/atmosphereBase.cpp"
  )
endif()
if(EXISTS "${_atm_base_impl}")
  list(APPEND PLUGIN_SOURCES "${_atm_base_impl}")
else()
  message(FATAL_ERROR "atmosphereBase.cpp not found in bsk_sdk runtime_min")
endif()

set(_lin_alg_impl
  "${CMAKE_CURRENT_SOURCE_DIR}/../../external/basilisk/src/architecture/utilities/linearAlgebra.c"
)
if(EXISTS "${_lin_alg_impl}")
  set_source_files_properties("${_lin_alg_impl}" PROPERTIES LANGUAGE C)
  list(APPEND PLUGIN_SOURCES "${_lin_alg_impl}")
endif()

# Build the SWIG module
bsk_add_swig_module(
  TARGET customExponentialAtmosphere
  INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}/swig/customExponentialAtmosphere.i"
  SOURCES ${PLUGIN_SOURCES}
  INCLUDE_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/src"
  LINK_LIBS ${BASILISK_RUNTIME_LIBS} bsk::arch_min
  OUTPUT_DIR "${PLUGIN_PKG_DIR}"
)

target_include_directories(customExponentialAtmosphere PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}/src"
  "${CMAKE_CURRENT_SOURCE_DIR}/messages"
)

# Generate message bindings into custom_atm/messaging
bsk_generate_messages(
  OUTPUT_DIR "${PLUGIN_PKG_DIR}/messaging"
  MSG_HEADERS
    "${CMAKE_CURRENT_SOURCE_DIR}/messages/CustomAtmStatusMsgPayload.h"
)

# Link against SDK-provided Basilisk minimal libs (if your plugin needs them)

