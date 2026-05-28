cmake_minimum_required(VERSION 3.20)
project(separatrix CXX C)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# LLVM 21 (pinned; resolve via -DLLVM_DIR=/path/to/llvm/lib/cmake/llvm).
find_package(LLVM REQUIRED CONFIG)
message(STATUS "Using LLVM ${LLVM_PACKAGE_VERSION} from ${LLVM_DIR}")

include_directories(SYSTEM ${LLVM_INCLUDE_DIRS})
separate_arguments(LLVM_DEFINITIONS_LIST NATIVE_COMMAND "${LLVM_DEFINITIONS}")
add_definitions(${LLVM_DEFINITIONS_LIST})

# LLVM is typically built without RTTI; match it to avoid link/codegen issues.
if(NOT LLVM_ENABLE_RTTI)
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fno-rtti")
endif()

add_executable(separatrix
  separatrix/cli/main.cpp
  separatrix/ir/graph.cpp
  separatrix/analyzer/builder.cpp)

target_include_directories(separatrix PRIVATE ${CMAKE_SOURCE_DIR})

llvm_map_components_to_libnames(LLVM_LIBS core irreader support)
target_link_libraries(separatrix PRIVATE ${LLVM_LIBS})
