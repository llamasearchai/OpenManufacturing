# This CMakeLists.txt is for C++ components that might be part of the 'openmanufacturing' Python package itself (e.g., C++ extensions).
# However, the primary C++ components for the OpenManufacturing project (like fast_alignment library)
# are currently built by the CMakeLists.txt at the root of the repository, using sources from 'OpenManufacturing/src/cpp/'.

# If you intend to build C++ extensions directly with this Python package (e.g., using scikit-build-core or similar),
# you would configure that here.

cmake_minimum_required(VERSION 3.14)
project(OpenManufacturingPackageCpp LANGUAGES CXX)

# Add a placeholder comment or leave this minimal if C++ parts are handled by the root CMakeLists.txt
# message(STATUS "openmanufacturing/CMakeLists.txt: Placeholder for package-specific C++ components.")
