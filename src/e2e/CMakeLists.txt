# End-to-end bot scenarios against a running development server.
#
#   bin/sapphire_e2e --list
#   bin/sapphire_e2e common.SayAndWalk --hold
#
# The client library speaks the FFXIV 3.3 lobby and zone protocol; the harness
# reads the server's own config next to the binary; scenarios live in
# scenarios/<group>/<Name>.cpp and register themselves with EXPOSE_SCENARIO.
get_filename_component(SAPPHIRE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
find_package(Threads REQUIRED)

# Protocol and request builders: no game data, no database, unit-testable.
add_library(sapphire_e2e_protocol STATIC
  client/Protocol.cpp
  client/CreationActions.cpp
  client/RewardsState.cpp
  client/InventoryActions.cpp
  client/ShopActions.cpp
  client/RespawnActions.cpp
  client/TransitionActions.cpp
  client/PartyActions.cpp
  client/ChatActions.cpp
  client/CombatState.cpp
  "${SAPPHIRE_ROOT}/src/common/Crypt/blowfish.cpp"
  "${SAPPHIRE_ROOT}/src/common/Crypt/md5.cpp"
  "${SAPPHIRE_ROOT}/src/common/Crypt/Random.cpp")
target_compile_features(sapphire_e2e_protocol PUBLIC cxx_std_17)
target_include_directories(sapphire_e2e_protocol PUBLIC
  "${CMAKE_CURRENT_SOURCE_DIR}/client"
  "${SAPPHIRE_ROOT}/src/common"
  "${SAPPHIRE_ROOT}/deps"
  "${SAPPHIRE_ROOT}/deps/datReader")
target_include_directories(sapphire_e2e_protocol SYSTEM PUBLIC
  "${SAPPHIRE_ROOT}/deps/asio/asio/include"
  "${SAPPHIRE_ROOT}/deps/nlohmann/include")
target_compile_definitions(sapphire_e2e_protocol PUBLIC ASIO_STANDALONE)
if(WIN32)
  target_compile_definitions(sapphire_e2e_protocol PUBLIC NOMINMAX _WIN32_WINNT=0x601 _CRT_SECURE_NO_WARNINGS
    _SILENCE_STDEXT_ARR_ITERS_DEPRECATION_WARNING _SILENCE_CXX17_RESULT_OF_DEPRECATION_WARNING)
  if(MSVC)
    target_compile_options(sapphire_e2e_protocol PUBLIC /bigobj /utf-8)
  endif()
  target_link_libraries(sapphire_e2e_protocol PUBLIC ws2_32 mswsock bcrypt)
endif()
target_link_libraries(sapphire_e2e_protocol PUBLIC Threads::Threads)

# The runner: client, harness and every scenario, linked against the server's common library.
file(GLOB_RECURSE SAPPHIRE_E2E_SCENARIOS CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/scenarios/*.cpp")
add_executable(sapphire_e2e
  runner/main.cpp
  client/Client.cpp
  client/ClientActions.cpp
  client/Bot.cpp
  harness/Scenario.cpp
  harness/Config.cpp
  harness/Server.cpp
  harness/GameData.cpp
  harness/Context.cpp
  harness/Content.cpp
  harness/NavigationRoute.cpp
  ${SAPPHIRE_E2E_SCENARIOS})
target_include_directories(sapphire_e2e PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
target_link_libraries(sapphire_e2e PRIVATE sapphire_e2e_protocol common Detour)

# One ctest entry per scenario file; they need the development stack running
# next to the binary, so they are skipped in a plain CI build.
if(BUILD_TESTING)
  foreach(scenario_file ${SAPPHIRE_E2E_SCENARIOS})
    get_filename_component(scenario_name "${scenario_file}" NAME_WE)
    get_filename_component(scenario_dir "${scenario_file}" DIRECTORY)
    get_filename_component(scenario_group "${scenario_dir}" NAME)
    add_test(NAME "e2e.${scenario_group}.${scenario_name}"
      COMMAND sapphire_e2e "${scenario_group}.${scenario_name}"
      WORKING_DIRECTORY "${SAPPHIRE_ROOT}/bin")
    set_tests_properties("e2e.${scenario_group}.${scenario_name}" PROPERTIES LABELS "e2e")
  endforeach()

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
  target_link_libraries(sapphire_protocol_tests PRIVATE sapphire_e2e_protocol)
  add_test(NAME sapphire_protocol COMMAND sapphire_protocol_tests)
  add_executable(sapphire_reward_tests "${SAPPHIRE_ROOT}/tests/protocol/test_rewards.cpp")
  target_link_libraries(sapphire_reward_tests PRIVATE sapphire_e2e_protocol)
  add_test(NAME sapphire_rewards COMMAND sapphire_reward_tests)
  add_executable(sapphire_combat_tests "${SAPPHIRE_ROOT}/tests/protocol/test_combat.cpp")
  target_link_libraries(sapphire_combat_tests PRIVATE sapphire_e2e_protocol)
  add_test(NAME sapphire_combat COMMAND sapphire_combat_tests)
  add_executable(sapphire_navigation_tests harness/NavigationRoute.cpp "${SAPPHIRE_ROOT}/tests/protocol/test_navigation.cpp")
  target_compile_features(sapphire_navigation_tests PRIVATE cxx_std_17)
  target_include_directories(sapphire_navigation_tests PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/harness")
  target_link_libraries(sapphire_navigation_tests PRIVATE Detour)
  add_test(NAME sapphire_navigation COMMAND sapphire_navigation_tests)
endif()
