add_library( sqlite3 STATIC sqlite3.c )
target_include_directories( sqlite3 PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}" )
target_compile_definitions( sqlite3 PRIVATE
  SQLITE_ENABLE_FTS5
  SQLITE_OMIT_LOAD_EXTENSION
  SQLITE_THREADSAFE=1
)
if( MSVC )
  target_compile_definitions( sqlite3 PRIVATE _CRT_SECURE_NO_WARNINGS )
endif()
