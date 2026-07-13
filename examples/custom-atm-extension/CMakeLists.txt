# =============================================================================
# Boilerplate: Copy and Paste this section as is, and modify the section below.
# =============================================================================
cmake_minimum_required(VERSION 3.26)
project(bsk_extension_exponential_atmosphere LANGUAGES C CXX)

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module NumPy)

# Locate bsk-sdk from the active Python environment
execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c
    "import bsk_sdk; print(bsk_sdk.cmake_config_dir(), end='')"
  OUTPUT_VARIABLE bsk_sdk_dir
  RESULT_VARIABLE rc
)
if(NOT rc EQUAL 0 OR bsk_sdk_dir STREQUAL "")
  message(FATAL_ERROR "bsk-sdk not found (is it installed in this Python environment?)")
endif()
file(TO_CMAKE_PATH "${bsk_sdk_dir}" bsk_sdk_dir)

set(bsk-sdk_DIR "${bsk_sdk_dir}")
find_package(bsk-sdk CONFIG REQUIRED)

# Where scikit-build-core places wheel outputs
set(EXTENSION_PKG_DIR "${SKBUILD_PLATLIB_DIR}/custom_atm")

# =============================================================================
# Extension-specific configuration
# =============================================================================

# Install a pure-Python Basilisk module into the same package as the compiled
# modules. Numba modules need no native build step of their own.
# Guide: https://avslab.github.io/basilisk/Learn/makingModules/numbaModules.html
bsk_add_python_module(
  SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/numbaAtmosphere/numbaAtmosphere.py"
  OUTPUT_DIR "${EXTENSION_PKG_DIR}"
)

# Gather your extension sources
file(GLOB EXTENSION_SOURCES CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/customExponentialAtmosphere/*.cpp"
)
# Note: do NOT add SDK sources (arch_min, arch_utilities, runtime_min, or
# built-in cMsgCInterface definitions) here.
# bsk_add_swig_module compiles them automatically into the extension target.
list(APPEND EXTENSION_SOURCES
  "${CMAKE_CURRENT_SOURCE_DIR}/planetStateProbe/planetStateProbe.c"
)

# Build the SWIG module. The SDK handles Python, SWIG, Eigen, and Basilisk
# library resolution automatically.
bsk_add_swig_module(
  TARGET customExponentialAtmosphere
  INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}/customExponentialAtmosphere/customExponentialAtmosphere.i"
  SOURCES   ${EXTENSION_SOURCES}
  INCLUDE_DIRS
    "${CMAKE_CURRENT_SOURCE_DIR}/customExponentialAtmosphere"
    "${CMAKE_CURRENT_SOURCE_DIR}/messages"
    "${CMAKE_CURRENT_SOURCE_DIR}/planetStateProbe"
  OUTPUT_DIR "${EXTENSION_PKG_DIR}"
)

# Generate Python bindings for extension-defined messages
bsk_generate_messages(
  OUTPUT_DIR "${EXTENSION_PKG_DIR}/messaging"
  MSG_HEADERS
    "${CMAKE_CURRENT_SOURCE_DIR}/messages/CustomAtmStatusMsgPayload.h"
)
