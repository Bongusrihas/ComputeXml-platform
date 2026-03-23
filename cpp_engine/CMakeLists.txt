cmake_minimum_required(VERSION 3.20)
project(computex_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)
FetchContent_Declare(
  csv_parser
  GIT_REPOSITORY https://github.com/vincentlaucsb/csv-parser.git
  GIT_TAG master
)
FetchContent_MakeAvailable(csv_parser)

find_package(BLAS QUIET)

if(NOT BLAS_FOUND AND DEFINED ENV{OPENBLAS_ROOT})
  set(OPENBLAS_ROOT "$ENV{OPENBLAS_ROOT}")
  find_path(OPENBLAS_INCLUDE_DIR
    NAMES cblas.h
    PATHS
      "${OPENBLAS_ROOT}"
      "${OPENBLAS_ROOT}/include"
      "${OPENBLAS_ROOT}/build/generated"
  )
  find_library(OPENBLAS_LIBRARY
    NAMES openblas libopenblas
    PATHS
      "${OPENBLAS_ROOT}/lib"
      "${OPENBLAS_ROOT}/lib64"
      "${OPENBLAS_ROOT}/build/lib"
      "${OPENBLAS_ROOT}/build/lib/Release"
  )
endif()

if(BLAS_FOUND)
  set(COMPUTEX_BLAS_LIBS BLAS::BLAS)
elseif(OPENBLAS_LIBRARY)
  set(COMPUTEX_BLAS_LIBS ${OPENBLAS_LIBRARY})
else()
  message(FATAL_ERROR "BLAS/OpenBLAS not found. Set OPENBLAS_ROOT if needed.")
endif()

find_package(CUDAToolkit QUIET)
include(CheckLanguage)

set(GPU_SOURCES
  src/linear_cublas.cu
  src/logistic_cublas.cu
)

if(CUDAToolkit_FOUND)
  check_language(CUDA)
endif()

if(CUDAToolkit_FOUND AND CMAKE_CUDA_COMPILER)
  enable_language(CUDA)
else()
  set_source_files_properties(${GPU_SOURCES} PROPERTIES LANGUAGE CXX)
endif()

add_executable(engine
  src/main.cpp
  src/parser.cpp
  src/metric_linear.cpp
  src/metric_logistic.cpp
  src/linear_open.cpp
  src/logistic_open.cpp
  ${GPU_SOURCES}
)

target_include_directories(engine PRIVATE include)
if(OPENBLAS_INCLUDE_DIR)
  target_include_directories(engine PRIVATE "${OPENBLAS_INCLUDE_DIR}")
endif()
if(DEFINED OPENBLAS_ROOT)
  target_include_directories(engine PRIVATE "${OPENBLAS_ROOT}/build")
endif()

target_link_libraries(engine PRIVATE csv ${COMPUTEX_BLAS_LIBS})

if(CUDAToolkit_FOUND AND CMAKE_CUDA_COMPILER)
  target_link_libraries(engine PRIVATE CUDA::cublas CUDA::cudart)
  target_compile_definitions(engine PRIVATE COMPUTEX_HAS_CUBLAS=1)
endif()
