cmake_minimum_required(VERSION 3.26)

# Compile both C and C++ sources
project(bsk_sdk LANGUAGES C CXX)

include(CMakePackageConfigHelpers)
include(GNUInstallDirs)

# Python wheel layout
set(BSK_SDK_INCLUDE_SRC_DIR       "${CMAKE_CURRENT_SOURCE_DIR}/src/bsk_sdk/include")
set(BSK_SDK_C_MSG_INTERFACE_DIR   "${BSK_SDK_INCLUDE_SRC_DIR}/cMsgCInterface")
set(BSK_ARCH_MIN_SRC_DIR          "${CMAKE_CURRENT_SOURCE_DIR}/src/bsk_sdk/arch_min")
set(BSK_ARCH_UTILITIES_SRC_DIR    "${CMAKE_CURRENT_SOURCE_DIR}/src/bsk_sdk/arch_utilities")
set(BSK_RUNTIME_MIN_SRC_DIR       "${CMAKE_CURRENT_SOURCE_DIR}/src/bsk_sdk/runtime_min")
set(BSK_SDK_COMPAT_INCLUDE_DIR    "${CMAKE_CURRENT_SOURCE_DIR}/src/bsk_sdk/include_compat")
set(BSK_SDK_SWIG_SRC_DIR          "${CMAKE_CURRENT_SOURCE_DIR}/src/bsk_sdk/swig")
set(BSK_SDK_TOOLS_SRC_DIR         "${CMAKE_CURRENT_SOURCE_DIR}/tools")

find_package(Eigen3 CONFIG QUIET)
if(NOT Eigen3_FOUND)
  include(FetchContent)
  FetchContent_Declare(
    Eigen3
    URL      https://gitlab.com/libeigen/eigen/-/archive/3.4.0/eigen-3.4.0.tar.gz
    URL_HASH SHA256=8586084f71f9bde545ee7fa6d00288b264a2b7ac3607b974e54d13e7162c1c72
    DOWNLOAD_EXTRACT_TIMESTAMP ON
  )
  set(EIGEN_BUILD_DOC     OFF CACHE BOOL "" FORCE)
  set(BUILD_TESTING       OFF CACHE BOOL "" FORCE)
  set(EIGEN_BUILD_PKGCONFIG OFF CACHE BOOL "" FORCE)
  FetchContent_MakeAvailable(Eigen3)
  message(STATUS "bsk-sdk: Eigen3 not found locally — downloaded via FetchContent")
endif()

# Bundle Eigen3 headers into the wheel so downstream consumers are self-contained.
if(DEFINED eigen3_SOURCE_DIR)
  set(_bsk_eigen3_src "${eigen3_SOURCE_DIR}")
else()
  get_target_property(_bsk_eigen3_incdirs Eigen3::Eigen INTERFACE_INCLUDE_DIRECTORIES)
  list(GET _bsk_eigen3_incdirs 0 _bsk_eigen3_src)
endif()

install(
  DIRECTORY "${_bsk_eigen3_src}/Eigen"
  DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/eigen3"
)
install(
  DIRECTORY "${_bsk_eigen3_src}/unsupported"
  DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/eigen3"
  OPTIONAL
)

# Header-only SDK target
add_library(bsk_sdk_headers INTERFACE)
add_library(bsk::sdk_headers ALIAS bsk_sdk_headers)

target_compile_features(bsk_sdk_headers INTERFACE cxx_std_17)

target_include_directories(bsk_sdk_headers INTERFACE
  $<BUILD_INTERFACE:${BSK_SDK_INCLUDE_SRC_DIR}>
  $<BUILD_INTERFACE:${BSK_SDK_C_MSG_INTERFACE_DIR}>
  $<BUILD_INTERFACE:${BSK_SDK_COMPAT_INCLUDE_DIR}>
  $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
  $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}/cMsgCInterface>
  $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}/compat>
  $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}/Basilisk>
)


install(
  DIRECTORY "${BSK_SDK_INCLUDE_SRC_DIR}/"
  DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
)

install(
  DIRECTORY "${BSK_SDK_COMPAT_INCLUDE_DIR}/"
  DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/compat"
)

install(
  DIRECTORY "${BSK_ARCH_MIN_SRC_DIR}/"
  DESTINATION "arch_min"
  FILES_MATCHING
    PATTERN "*.c"
    PATTERN "*.cpp"
)

install(
  DIRECTORY "${BSK_ARCH_UTILITIES_SRC_DIR}/"
  DESTINATION "arch_utilities"
  FILES_MATCHING
    PATTERN "*.c"
    PATTERN "*.cpp"
)

install(
  DIRECTORY "${BSK_RUNTIME_MIN_SRC_DIR}/"
  DESTINATION "runtime_min"
  FILES_MATCHING
    PATTERN "*.c"
    PATTERN "*.cpp"
    PATTERN "*.h"
)

install(
  DIRECTORY "${BSK_SDK_SWIG_SRC_DIR}/"
  DESTINATION "swig"
  COMPONENT python
)

install(
  DIRECTORY "${BSK_SDK_TOOLS_SRC_DIR}/"
  DESTINATION "tools"
  PATTERN "__pycache__" EXCLUDE
)

install(
  FILES
    "${CMAKE_CURRENT_SOURCE_DIR}/src/bsk_sdk/__init__.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/bsk_sdk/_bsk_version.txt"
  DESTINATION "."
)

configure_package_config_file(
  cmake/bsk-sdkConfig.cmake.in
  "${CMAKE_CURRENT_BINARY_DIR}/bsk-sdkConfig.cmake"
  INSTALL_DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/bsk-sdk"
)

write_basic_package_version_file(
  "${CMAKE_CURRENT_BINARY_DIR}/bsk-sdkConfigVersion.cmake"
  VERSION ${SKBUILD_PROJECT_VERSION}
  COMPATIBILITY SameMajorVersion
)

install(
  FILES
    "${CMAKE_CURRENT_BINARY_DIR}/bsk-sdkConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/bsk-sdkConfigVersion.cmake"
  DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/bsk-sdk"
)

install(
  FILES
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/bsk_add_swig_module.cmake"
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/bsk_add_python_module.cmake"
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/bsk_generate_messages.cmake"
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/bsk_add_rust_module.cmake"
  DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/bsk-sdk"
)
