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

cmake_minimum_required(VERSION 3.26)
project(bsk_sdk_shared_runtime_test LANGUAGES C CXX)

if(NOT DEFINED BSK_SDK_CMAKE_DIR)
  message(FATAL_ERROR "BSK_SDK_CMAKE_DIR is required")
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(_fixture_root "${CMAKE_CURRENT_BINARY_DIR}/fixture")
set(BSK_SDK_INCLUDE_DIR "${_fixture_root}/include")
set(BSK_SDK_ARCH_MIN_DIR "${_fixture_root}/arch_min")
set(BSK_SDK_ARCH_UTILITIES_DIR "${_fixture_root}/arch_utilities")
set(BSK_SDK_RUNTIME_MIN_DIR "${_fixture_root}/runtime_min")
set(BSK_SDK_C_MSG_INTERFACE_DIR "${_fixture_root}/cMsgCInterface")
set(BSK_SDK_MSG_AUTOSOURCE_DIR "${_fixture_root}/msgAutoSource")
file(MAKE_DIRECTORY
  "${BSK_SDK_INCLUDE_DIR}"
  "${BSK_SDK_ARCH_MIN_DIR}"
  "${BSK_SDK_ARCH_UTILITIES_DIR}"
  "${BSK_SDK_RUNTIME_MIN_DIR}"
  "${BSK_SDK_C_MSG_INTERFACE_DIR}"
  "${_fixture_root}/consumers"
  "${BSK_SDK_MSG_AUTOSOURCE_DIR}"
)
file(WRITE "${BSK_SDK_ARCH_MIN_DIR}/arch_min.cpp"
  "int bsk_sdk_test_arch_min(void) { return 1; }\n")
file(WRITE "${BSK_SDK_ARCH_UTILITIES_DIR}/arch_utility.c"
  "int bsk_sdk_test_arch_utility(void) { return 2; }\n")
file(WRITE "${BSK_SDK_RUNTIME_MIN_DIR}/runtime_min.cpp"
  "int bsk_sdk_test_runtime_min(void) { return 3; }\n")
file(WRITE "${BSK_SDK_C_MSG_INTERFACE_DIR}/BuiltInMsg_C.cpp"
  "int bsk_sdk_test_builtin_message(void) { return 4; }\n")
file(WRITE "${_fixture_root}/consumers/extension_dependency.cpp"
  "int bsk_sdk_test_runtime_min(void);\n"
  "int bsk_sdk_test_extension_dependency(void) {\n"
  "  return bsk_sdk_test_runtime_min();\n"
  "}\n")
file(WRITE "${_fixture_root}/consumers/extension_consumer.cpp"
  "int bsk_sdk_test_extension_dependency(void);\n"
  "int bsk_sdk_test_extension_consumer(void) {\n"
  "  return bsk_sdk_test_extension_dependency();\n"
  "}\n")
file(WRITE "${_fixture_root}/consumers/message_dependency.cpp"
  "int bsk_sdk_test_runtime_min(void);\n"
  "int bsk_sdk_test_message_dependency(void) {\n"
  "  return bsk_sdk_test_runtime_min();\n"
  "}\n")
file(WRITE "${_fixture_root}/consumers/message_consumer.cpp"
  "int bsk_sdk_test_message_dependency(void);\n"
  "int bsk_sdk_test_message_consumer(void) {\n"
  "  return bsk_sdk_test_message_dependency();\n"
  "}\n")
file(WRITE "${_fixture_root}/extension_consumer.i" "")
file(WRITE "${_fixture_root}/FixtureMsgPayload.h"
  "struct FixtureMsgPayload { int value; };\n")

file(WRITE "${BSK_SDK_MSG_AUTOSOURCE_DIR}/generatePayloadMetaJson.py" [=[
from pathlib import Path
import sys

output = Path(sys.argv[3])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text("{}\n", encoding="utf-8")
if "--depfile" in sys.argv:
    depfile = Path(sys.argv[sys.argv.index("--depfile") + 1])
    depfile.write_text("", encoding="utf-8")
]=])
file(WRITE "${BSK_SDK_MSG_AUTOSOURCE_DIR}/generatePayloadEqualityHeader.py" [=[
from pathlib import Path
import sys

Path(sys.argv[1]).write_text("#pragma once\n", encoding="utf-8")
]=])
file(WRITE "${BSK_SDK_MSG_AUTOSOURCE_DIR}/generateSWIGModules.py" [=[
from pathlib import Path
import sys

Path(sys.argv[1]).write_text("%module FixtureMsgPayload\n", encoding="utf-8")
]=])
file(WRITE "${BSK_SDK_MSG_AUTOSOURCE_DIR}/msgInterfacePy.i.in" "")
file(WRITE "${BSK_SDK_MSG_AUTOSOURCE_DIR}/cMsgCInterfacePy.i.in" "")

add_library(bsk::sdk_headers INTERFACE IMPORTED GLOBAL)
add_library(Eigen3::Eigen INTERFACE IMPORTED GLOBAL)

include("${BSK_SDK_CMAKE_DIR}/bsk_generate_messages.cmake")

# Replace the build-tool plumbing with small test doubles while retaining the
# production public helpers and shared-runtime resolver under test.
macro(_bsk_find_build_deps)
endmacro()

function(_bsk_collect_swig_flags out_var)
  set(${out_var} "" PARENT_SCOPE)
endfunction()

function(swig_add_library target_name)
  if(target_name STREQUAL "extension_consumer")
    set(_source "${_fixture_root}/consumers/extension_consumer.cpp")
  else()
    set(_source "${_fixture_root}/consumers/message_consumer.cpp")
  endif()
  add_library(${target_name} MODULE "${_source}")
endfunction()

function(_bsk_configure_swig_target target_name output_dir link_libs extra_include_dirs)
  target_link_libraries(${target_name} PRIVATE ${link_libs})
endfunction()

add_library(extension_dependency STATIC
  "${_fixture_root}/consumers/extension_dependency.cpp")
add_library(message_dependency STATIC
  "${_fixture_root}/consumers/message_dependency.cpp")
set_target_properties(extension_dependency message_dependency PROPERTIES
  POSITION_INDEPENDENT_CODE ON
)

bsk_add_swig_module(
  TARGET extension_consumer
  INTERFACE "${_fixture_root}/extension_consumer.i"
  LINK_LIBS extension_dependency
  OUTPUT_DIR "${_fixture_root}/output"
)
bsk_generate_messages(
  OUTPUT_DIR "${_fixture_root}/output/messages"
  OUT_VAR _generated_message_targets
  MSG_HEADERS "${_fixture_root}/FixtureMsgPayload.h"
  TARGET_LINK_LIBS message_dependency
)

if(NOT TARGET extension_consumer OR NOT TARGET FixtureMsgPayload)
  message(FATAL_ERROR
    "The public extension and message helpers did not create their targets")
endif()
if(NOT _generated_message_targets STREQUAL "FixtureMsgPayload")
  message(FATAL_ERROR
    "bsk_generate_messages did not return its generated message target")
endif()
if(NOT TARGET bsk_sdk_runtime_static OR NOT TARGET bsk::sdk_runtime)
  message(FATAL_ERROR "The shared SDK runtime target and alias must exist")
endif()

function(_assert_runtime_linked_last target_name expected_dependency)
  get_target_property(_link_libs ${target_name} LINK_LIBRARIES)
  list(FIND _link_libs "${expected_dependency}" _dependency_link_index)
  list(FIND _link_libs "bsk::sdk_runtime" _runtime_link_index)
  list(LENGTH _link_libs _link_count)
  math(EXPR _last_link_index "${_link_count} - 1")
  if(_dependency_link_index EQUAL -1)
    message(FATAL_ERROR
      "${target_name} does not link ${expected_dependency}: ${_link_libs}")
  endif()
  if(NOT _runtime_link_index EQUAL _last_link_index)
    message(FATAL_ERROR
      "${target_name} must link bsk::sdk_runtime after consumer libraries: "
      "${_link_libs}")
  endif()
endfunction()

_assert_runtime_linked_last(extension_consumer extension_dependency)
_assert_runtime_linked_last(FixtureMsgPayload message_dependency)

get_target_property(_aliased_target bsk::sdk_runtime ALIASED_TARGET)
if(NOT _aliased_target STREQUAL "bsk_sdk_runtime_static")
  message(FATAL_ERROR "bsk::sdk_runtime must alias bsk_sdk_runtime_static")
endif()

get_target_property(_runtime_sources bsk_sdk_runtime_static SOURCES)
set(_expected_sources
  "${BSK_SDK_ARCH_MIN_DIR}/arch_min.cpp"
  "${BSK_SDK_ARCH_UTILITIES_DIR}/arch_utility.c"
  "${BSK_SDK_RUNTIME_MIN_DIR}/runtime_min.cpp"
  "${BSK_SDK_C_MSG_INTERFACE_DIR}/BuiltInMsg_C.cpp"
)
foreach(_expected_source IN LISTS _expected_sources)
  list(FIND _runtime_sources "${_expected_source}" _source_index)
  if(_source_index EQUAL -1)
    message(FATAL_ERROR
      "Shared runtime is missing expected source: ${_expected_source}")
  endif()
endforeach()
list(LENGTH _runtime_sources _runtime_source_count)
list(LENGTH _expected_sources _expected_source_count)
if(NOT _runtime_source_count EQUAL _expected_source_count)
  message(FATAL_ERROR
    "Shared runtime sources were duplicated or unexpected sources were added: "
    "${_runtime_sources}")
endif()

get_property(_directory_targets DIRECTORY PROPERTY BUILDSYSTEM_TARGETS)
set(_runtime_target_count 0)
foreach(_target IN LISTS _directory_targets)
  if(_target STREQUAL "bsk_sdk_runtime_static")
    math(EXPR _runtime_target_count "${_runtime_target_count} + 1")
  endif()
endforeach()
if(NOT _runtime_target_count EQUAL 1)
  message(FATAL_ERROR
    "Expected one shared SDK runtime target, found ${_runtime_target_count}")
endif()

function(_bsk_resolve_basilisk_libs out_var)
  set(${out_var} "fallback_basilisk_runtime" PARENT_SCOPE)
endfunction()
set(BSK_SDK_ARCH_MIN_DIR "${CMAKE_CURRENT_SOURCE_DIR}/missing")
_bsk_resolve_sdk_sources(_fallback_link_libs)
if(NOT _fallback_link_libs STREQUAL "fallback_basilisk_runtime")
  message(FATAL_ERROR "Fallback resolution did not return Basilisk runtime libraries")
endif()
