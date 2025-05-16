cmake_minimum_required(VERSION 3.14)
project(OpenManufacturing VERSION 1.0.0)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Apple-specific settings
if(APPLE)
    set(CMAKE_MACOSX_RPATH 1)
    set(CMAKE_INSTALL_RPATH "@executable_path;@executable_path/../lib")
endif()

# Find required packages
find_package(Boost REQUIRED COMPONENTS system filesystem thread)

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${Boost_INCLUDE_DIRS}
)

# Add the C++ library
add_library(fast_alignment SHARED
    src/cpp/alignment/fast_align.cpp
)

# Link libraries
target_link_libraries(fast_alignment
    ${Boost_LIBRARIES}
)

# Installation rules
install(TARGETS fast_alignment
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)