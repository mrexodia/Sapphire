# Also buildable on its own, without MySQL or game assets:
# cmake -S src/test_client -B build-e2e
cmake_minimum_required(VERSION 3.22)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  project(SapphireTestClient LANGUAGES CXX)
  include(CTest)
endif()
get_filename_component(SAPPHIRE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR AND BUILD_TESTING)
  set(RECASTNAVIGATION_DEMO OFF CACHE BOOL "" FORCE)
  set(RECASTNAVIGATION_TESTS OFF CACHE BOOL "" FORCE)
  set(RECASTNAVIGATION_EXAMPLES OFF CACHE BOOL "" FORCE)
  set(RECASTNAVIGATION_DT_POLYREF64 ON CACHE BOOL "" FORCE)
  add_subdirectory("${SAPPHIRE_ROOT}/deps/recastnavigation" "${CMAKE_CURRENT_BINARY_DIR}/recast" EXCLUDE_FROM_ALL)
endif()
find_package(Threads REQUIRED)
add_library(sapphire_test_protocol STATIC
  Protocol.cpp
  RewardsState.cpp
  InventoryActions.cpp
  ShopActions.cpp
  RespawnActions.cpp
  TransitionActions.cpp
  CombatState.cpp
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
  add_executable(sapphire_test_combat_catalog CombatCatalog.cpp)
  target_link_libraries(sapphire_test_combat_catalog PRIVATE common)
  add_executable(sapphire_test_shop_catalog ShopCatalog.cpp NavigationRoute.cpp)
  target_link_libraries(sapphire_test_shop_catalog PRIVATE common)
  add_executable(sapphire_test_respawn_catalog RespawnCatalog.cpp)
  target_link_libraries(sapphire_test_respawn_catalog PRIVATE common)
  add_executable(sapphire_test_pursuit_catalog PursuitCatalog.cpp NavigationRoute.cpp)
  target_link_libraries(sapphire_test_pursuit_catalog PRIVATE common)
  add_executable(sapphire_test_transitions TransitionCatalog.cpp NavigationRoute.cpp)
  target_link_libraries(sapphire_test_transitions PRIVATE common)
  add_executable(sapphire_test_catalog Catalog.cpp NavigationRoute.cpp)
  target_link_libraries(sapphire_test_catalog PRIVATE common)
  set(NAV_EXPORT "${SAPPHIRE_ROOT}/src/tools/nav_export")
  add_executable(sapphire_test_navbuild BuildNavigation.cpp
    "${NAV_EXPORT}/nav/TiledNavmeshGenerator.cpp"
    "${NAV_EXPORT}/nav/ext/MeshLoaderObj.cpp"
    "${NAV_EXPORT}/nav/ext/ChunkyTriMesh.cpp")
  target_link_libraries(sapphire_test_navbuild PRIVATE common Recast DetourTileCache)
  target_include_directories(sapphire_test_navbuild PRIVATE "${NAV_EXPORT}"
    "${SAPPHIRE_ROOT}/deps/recastnavigation/DebugUtils/Include"
    "${SAPPHIRE_ROOT}/deps/recastnavigation/RecastDemo/Include")
endif()
add_executable(sapphire_test_client main.cpp Client.cpp)
target_link_libraries(sapphire_test_client PRIVATE sapphire_test_protocol)
if(BUILD_TESTING)
  add_executable(sapphire_item_id_tests "${SAPPHIRE_ROOT}/tests/world/test_item_id_allocator.cpp")
  target_compile_features(sapphire_item_id_tests PRIVATE cxx_std_17)
  target_include_directories(sapphire_item_id_tests PRIVATE "${SAPPHIRE_ROOT}/src/world")
  target_link_libraries(sapphire_item_id_tests PRIVATE Threads::Threads)
  add_test(NAME sapphire_item_ids COMMAND sapphire_item_id_tests)
  add_executable(sapphire_database_binding_tests
    "${SAPPHIRE_ROOT}/tests/database/test_prepared_statement.cpp"
    "${SAPPHIRE_ROOT}/src/common/Database/PreparedStatement.cpp")
  target_compile_features(sapphire_database_binding_tests PRIVATE cxx_std_17)
  target_include_directories(sapphire_database_binding_tests PRIVATE
    "${SAPPHIRE_ROOT}/tests/database/fakes" "${SAPPHIRE_ROOT}/src/common/Database")
  add_test(NAME sapphire_database_bindings COMMAND sapphire_database_binding_tests)
  add_executable(sapphire_protocol_tests "${SAPPHIRE_ROOT}/tests/protocol/test_protocol.cpp")
  target_link_libraries(sapphire_protocol_tests PRIVATE sapphire_test_protocol)
  add_test(NAME sapphire_protocol COMMAND sapphire_protocol_tests)
  add_executable(sapphire_reward_tests "${SAPPHIRE_ROOT}/tests/protocol/test_rewards.cpp")
  target_link_libraries(sapphire_reward_tests PRIVATE sapphire_test_protocol)
  add_test(NAME sapphire_rewards COMMAND sapphire_reward_tests)
  add_executable(sapphire_combat_tests "${SAPPHIRE_ROOT}/tests/protocol/test_combat.cpp")
  target_link_libraries(sapphire_combat_tests PRIVATE sapphire_test_protocol)
  add_test(NAME sapphire_combat COMMAND sapphire_combat_tests)
  add_executable(sapphire_navigation_tests NavigationRoute.cpp "${SAPPHIRE_ROOT}/tests/protocol/test_navigation.cpp")
  target_compile_features(sapphire_navigation_tests PRIVATE cxx_std_17)
  target_include_directories(sapphire_navigation_tests PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  target_link_libraries(sapphire_navigation_tests PRIVATE Detour)
  add_test(NAME sapphire_navigation COMMAND sapphire_navigation_tests)
endif()
