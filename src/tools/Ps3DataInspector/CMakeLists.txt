add_executable( ps3_data_inspector main.cpp )
target_link_libraries( ps3_data_inspector PRIVATE xivdatps3 )
target_include_directories( ps3_data_inspector SYSTEM PRIVATE "${PROJECT_SOURCE_DIR}/deps/nlohmann/include" )

if( BUILD_TESTING )
  add_executable( ps3_data_inspector_tests tests.cpp )
  target_link_libraries( ps3_data_inspector_tests PRIVATE xivdatps3 )
  target_include_directories( ps3_data_inspector_tests SYSTEM PRIVATE "${PROJECT_SOURCE_DIR}/deps/nlohmann/include" )
  add_test( NAME ps3_data_inspector_tests COMMAND ps3_data_inspector_tests )

  # Opt-in corpus check of the actual Toolkit wrapper, without graphics/DB.
  add_executable( ps3_toolkit_data_smoke toolkit_data_smoke.cpp ../ToolkitPs3/ExdData.cpp )
  target_link_libraries( ps3_toolkit_data_smoke PRIVATE common xivdatps3 )
endif()
