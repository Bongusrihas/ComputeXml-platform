cmake_minimum_required(VERSION 3.20)
project(computex_engine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)
FetchContent_Declare(
  csv_parser
  GIT_REPOSITORY https://github.com/vincentlaucsb/csv-parser.git
  GIT_TAG master
)
FetchContent_MakeAvailable(csv_parser)

find_package(BLAS REQUIRED)
find_package(CUDAToolkit QUIET)

add_executable(engine
  src/main.cpp
  src/parser.cpp
  src/ohe.cpp
  src/le.cpp
  src/openblas_models.cpp
  src/cublas_models.cpp
)

target_include_directories(engine PRIVATE include)
target_link_libraries(engine PRIVATE csv BLAS::BLAS)

if (CUDAToolkit_FOUND)
  target_link_libraries(engine PRIVATE CUDA::cublas CUDA::cudart)
  target_compile_definitions(engine PRIVATE COMPUTEX_HAS_CUBLAS=1)
endif()
