# Also buildable on its own, without MySQL or game assets:
# cmake -S src/test_client -B build-e2e
cmake_minimum_required(VERSION 3.22)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  project(SapphireTestClient LANGUAGES CXX)
  include(CTest)
endif()
get_filename_component(SAPPHIRE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
find_package(Threads REQUIRED)
add_library(sapphire_test_protocol STATIC
  Protocol.cpp
  "${SAPPHIRE_ROOT}/src/common/Crypt/blowfish.cpp"
  "${SAPPHIRE_ROOT}/src/common/Crypt/md5.cpp"
  "${SAPPHIRE_ROOT}/src/common/Crypt/Random.cpp")
target_compile_features(sapphire_test_protocol PUBLIC cxx_std_17)
target_include_directories(sapphire_test_protocol PUBLIC
  "${CMAKE_CURRENT_SOURCE_DIR}"
  "${SAPPHIRE_ROOT}/src/common"
  "${SAPPHIRE_ROOT}/deps"
  "${SAPPHIRE_ROOT}/deps/datReader")
target_include_directories(sapphire_test_protocol SYSTEM PUBLIC
  "${SAPPHIRE_ROOT}/deps/asio/asio/include"
  "${SAPPHIRE_ROOT}/deps/nlohmann/include")
target_compile_definitions(sapphire_test_protocol PUBLIC ASIO_STANDALONE)
if(WIN32)
  target_compile_definitions(sapphire_test_protocol PUBLIC NOMINMAX _WIN32_WINNT=0x0601 _CRT_SECURE_NO_WARNINGS
    _SILENCE_STDEXT_ARR_ITERS_DEPRECATION_WARNING _SILENCE_CXX17_RESULT_OF_DEPRECATION_WARNING)
  if(MSVC)
    target_compile_options(sapphire_test_protocol PUBLIC /bigobj /utf-8)
  endif()
  target_link_libraries(sapphire_test_protocol PUBLIC ws2_32 mswsock bcrypt)
endif()
target_link_libraries(sapphire_test_protocol PUBLIC Threads::Threads)
if(NOT CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  add_executable(sapphire_test_catalog Catalog.cpp)
  target_link_libraries(sapphire_test_catalog PRIVATE common)
endif()
add_executable(sapphire_test_client main.cpp Client.cpp)
target_link_libraries(sapphire_test_client PRIVATE sapphire_test_protocol)
if(BUILD_TESTING)
  add_executable(sapphire_protocol_tests "${SAPPHIRE_ROOT}/tests/protocol/test_protocol.cpp")
  target_link_libraries(sapphire_protocol_tests PRIVATE sapphire_test_protocol)
  add_test(NAME sapphire_protocol COMMAND sapphire_protocol_tests)
endif()
