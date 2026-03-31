# =============================================================================
# Boilerplate: Copy and Paste this section as is, and modify the section below.
# =============================================================================
cmake_minimum_required(VERSION 3.26)
project(bsk_plugin_exponential_atmosphere LANGUAGES C CXX)

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
set(PLUGIN_PKG_DIR "${SKBUILD_PLATLIB_DIR}/custom_atm")

# =============================================================================
# Plugin-specific configuration
# =============================================================================

# Gather your plugin sources
file(GLOB PLUGIN_SOURCES CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/customExponentialAtmosphere/*.cpp"
)

# This plugin subclasses AtmosphereBase, so we need its implementation.
# The SDK ships it in runtime_min/ for exactly this purpose.
list(APPEND PLUGIN_SOURCES "${BSK_SDK_RUNTIME_MIN_DIR}/atmosphereBase.cpp")

# Build the SWIG module. The SDK handles Python, SWIG, Eigen, and Basilisk
# library resolution automatically.
bsk_add_swig_module(
  TARGET customExponentialAtmosphere
  INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}/customExponentialAtmosphere/customExponentialAtmosphere.i"
  SOURCES   ${PLUGIN_SOURCES}
  INCLUDE_DIRS
    "${CMAKE_CURRENT_SOURCE_DIR}/customExponentialAtmosphere"
    "${CMAKE_CURRENT_SOURCE_DIR}/messages"
  OUTPUT_DIR "${PLUGIN_PKG_DIR}"
)

# Generate Python bindings for plugin-defined messages
bsk_generate_messages(
  OUTPUT_DIR "${PLUGIN_PKG_DIR}/messaging"
  MSG_HEADERS
    "${CMAKE_CURRENT_SOURCE_DIR}/messages/CustomAtmStatusMsgPayload.h"
)
