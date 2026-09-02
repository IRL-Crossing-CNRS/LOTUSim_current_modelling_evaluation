cmake_minimum_required(VERSION 3.10.2 FATAL_ERROR)

find_package(gz-cmake3 REQUIRED)

project(GaussMarkov)

find_package(Eigen3 REQUIRED)
find_package(gz-plugin2 REQUIRED COMPONENTS register)
find_package(gz-math7 REQUIRED)
find_package(gz-transport13 REQUIRED)
find_package(gz-sim8 REQUIRED)

set(GZ_PLUGIN_VER ${gz-plugin2_VERSION_MAJOR})

# GaussMarkov Library
add_library(GaussMarkov SHARED UnderwaterCurrentPlugin.cc GaussMarkovProcess.cc)
set_property(TARGET GaussMarkov PROPERTY CXX_STANDARD 17)
target_include_directories(GaussMarkov PRIVATE ${EIGEN3_INCLUDE_DIRS})
target_link_libraries(GaussMarkov
  PRIVATE gz-plugin${GZ_PLUGIN_VER}::gz-plugin${GZ_PLUGIN_VER}
  PRIVATE gz-sim8::gz-sim8)

# Install both libraries
install(TARGETS GaussMarkov DESTINATION ${CMAKE_INSTALL_PREFIX}/lib)
