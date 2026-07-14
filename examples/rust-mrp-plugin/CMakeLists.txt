cmake_minimum_required(VERSION 3.26)
project(rust_mrp_plugin LANGUAGES C CXX)
include(CTest)

# ==========================================================================
# Boilerplate: locate bsk-sdk from the active Python environment
# ==========================================================================
find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module NumPy)

execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c
    "import bsk_sdk; print(bsk_sdk.cmake_config_dir(), end='')"
  OUTPUT_VARIABLE bsk_sdk_dir
  RESULT_VARIABLE rc
)
if(NOT rc EQUAL 0 OR bsk_sdk_dir STREQUAL "")
  message(FATAL_ERROR "bsk-sdk not found — run: pip install bsk-sdk")
endif()
file(TO_CMAKE_PATH "${bsk_sdk_dir}" bsk_sdk_dir)
set(bsk-sdk_DIR "${bsk_sdk_dir}")
find_package(bsk-sdk CONFIG REQUIRED)

# For wheel builds SKBUILD_PLATLIB_DIR is set by scikit-build-core. Direct
# CMake builds place a complete Python package under the build tree so neither
# generated SWIG files nor native extensions modify the source tree.
if(DEFINED SKBUILD_PLATLIB_DIR AND NOT SKBUILD_PLATLIB_DIR STREQUAL "")
  set(PKG_DIR "${SKBUILD_PLATLIB_DIR}/mrpRustController")
else()
  set(PKG_DIR "${CMAKE_CURRENT_BINARY_DIR}/python/mrpRustController")
endif()
file(MAKE_DIRECTORY "${PKG_DIR}")
configure_file(
  "${CMAKE_CURRENT_SOURCE_DIR}/mrpRustController/__init__.py"
  "${PKG_DIR}/__init__.py"
  COPYONLY
)

# ==========================================================================
# Plugin-specific: one call is all it takes
# ==========================================================================
bsk_add_rust_module(
  TARGET     mrpRustController
  MANIFEST   "${CMAKE_CURRENT_SOURCE_DIR}/mrpRustController/Cargo.toml"
  OUTPUT_DIR "${PKG_DIR}"
  # No HEADER needed: bsk-build generates it under the CMake build tree from
  # the Rust struct at cargo-build time.
)

# Install the package initializer into scikit-build-core's wheel staging area.
install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/mrpRustController/__init__.py"
        DESTINATION "${PKG_DIR}")

if(BUILD_TESTING)
  add_test(
    NAME rust_mrp_plugin_tests
    COMMAND "${Python3_EXECUTABLE}" -m pytest
      --import-mode=importlib
      "${CMAKE_CURRENT_SOURCE_DIR}/mrpRustController/_UnitTest"
      -v
  )
  set_tests_properties(rust_mrp_plugin_tests PROPERTIES
    WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    ENVIRONMENT "PYTHONPATH=${CMAKE_CURRENT_BINARY_DIR}/python"
  )
endif()
