// sapphire_e2e: runs bot scenarios against the development server next to it.
//
//   sapphire_e2e --list
//   sapphire_e2e common.SayAndWalk --hold
//   sapphire_e2e --filter combat.
//   sapphire_e2e                      (every scenario)
#include "../harness/Config.h"
#include "../harness/Context.h"
#include "../harness/GameData.h"
#include "../harness/Scenario.h"
#include "../harness/Server.h"
#include <Logging/Logger.h>
#include <Util/Paths.h>
#include <asio.hpp>
#include <chrono>
#include <cstring>
#include <fstream>
#include <iostream>
#include <thread>

using namespace Sapphire::E2E;

namespace
{
  std::string timestamp()
  {
    const auto now = std::chrono::system_clock::now();
    const auto time = std::chrono::system_clock::to_time_t( now );
    const auto millis = std::chrono::duration_cast< std::chrono::milliseconds >( now.time_since_epoch() ).count() % 1000;
    char buffer[ 32 ];
    std::tm local{};
#ifdef _WIN32
    localtime_s( &local, &time );
#else
    localtime_r( &time, &local );
#endif
    std::strftime( buffer, sizeof( buffer ), "%H:%M:%S", &local );
    char out[ 48 ];
    std::snprintf( out, sizeof( out ), "%s.%03d", buffer, static_cast< int >( millis ) );
    return out;
  }

  void usage()
  {
    std::cout <<
      "usage: sapphire_e2e [options] [scenario ...]\n"
      "  --list              list scenarios and exit\n"
      "  --filter PREFIX     run scenarios whose name starts with PREFIX (e.g. combat.)\n"
      "  --hold              keep the bots in the world after a scenario until Enter is pressed\n"
      "  --keep-bots         do not purge bot_ accounts before and after the run\n"
      "  --duration SECONDS  how long a long-running scenario (soak) keeps going\n"
      "  --bots N            bot count for scenarios that take one\n"
      "  --server-dir DIR    the server's bin directory (default: the runner's own directory)\n"
      "  --api HOST:PORT     API address (default: RestHost/RestPort from global.ini)\n"
      "  --secret SECRET     server secret (default: ServerSecret from global.ini)\n";
  }

  void writeJournal( const std::filesystem::path& directory, Bot& bot )
  {
    std::filesystem::create_directories( directory );
    std::ofstream file( directory / ( bot.name() + ".log" ) );
    const auto rows = bot.journal();
    for( const auto& row : rows )
    {
      const auto offset = std::chrono::duration_cast< std::chrono::milliseconds >( row.at - rows.front().at ).count();
      file << offset << "ms " << row.event << " " << row.data.dump() << '\n';
    }
  }
}

int main( int argc, char** argv )
{
  std::vector< std::string > names;
  std::string filter, serverDir, api, secret;
  bool list = false;
  Options options;
  for( int i = 1; i < argc; ++i )
  {
    const std::string arg = argv[ i ];
    auto value = [ & ]() -> std::string {
      if( i + 1 >= argc ) { std::cerr << arg << " needs a value\n"; std::exit( 2 ); }
      return argv[ ++i ];
    };
    if( arg == "--list" ) list = true;
    else if( arg == "--filter" ) filter = value();
    else if( arg == "--hold" ) options.hold = true;
    else if( arg == "--keep-bots" ) options.keepBots = true;
    else if( arg == "--duration" ) options.duration = std::stod( value() );
    else if( arg == "--bots" ) options.bots = static_cast< unsigned >( std::stoul( value() ) );
    else if( arg == "--server-dir" ) serverDir = value();
    else if( arg == "--api" ) api = value();
    else if( arg == "--secret" ) secret = value();
    else if( arg == "--help" || arg == "-h" ) { usage(); return 0; }
    else if( !arg.empty() && arg[ 0 ] == '-' ) { std::cerr << "unknown option " << arg << "\n"; usage(); return 2; }
    else names.push_back( arg );
  }

  auto& registry = Registry::instance();
  if( list )
  {
    for( const auto& [ name, info ] : registry.all() )
      std::cout << name << "\n";
    return 0;
  }

  std::vector< const ScenarioInfo* > selected;
  for( const auto& name : names )
  {
    const auto* info = registry.find( name );
    if( !info ) { std::cerr << "unknown scenario " << name << " (see --list)\n"; return 2; }
    selected.push_back( info );
  }
  if( names.empty() )
    for( const auto& [ name, info ] : registry.all() )
      if( filter.empty() || name.rfind( filter, 0 ) == 0 )
        selected.push_back( &info );
  if( selected.empty() ) { std::cerr << "no scenarios selected\n"; return 2; }

  auto log = []( const std::string& line ) { std::cout << timestamp() << " " << line << std::endl; };

  try
  {
    const auto directory = serverDir.empty() ? Sapphire::Common::Util::executableDir() : std::filesystem::path( serverDir );
    const auto config = Config::load( directory, api, secret );
    Sapphire::Logger::init( ( config.serverDir / "log" / "e2e" ).string() );
    Sapphire::Logger::setLogLevel( 4 ); // library noise (navmesh, exd) goes to the file, not the console
    Server server( config.apiHost, config.apiPort, config.secret );
    server.checkAlive();
    log( "development server at http://" + config.apiHost + ":" + std::to_string( config.apiPort ) );
    log( "loading game data from " + config.dataPath.string() );
    GameData data( config.dataPath, config.meshPath );
    if( !options.keepBots )
    {
      const auto purged = server.purgeBots();
      log( "purged " + std::to_string( purged.value( "deleted_accounts", 0 ) ) + " offline bot accounts" );
    }

    asio::io_service io;
    auto work = std::make_unique< asio::io_service::work >( io );
    std::thread thread( [ & ] { io.run(); } );
    const auto runStamp = [] {
      const auto time = std::chrono::system_clock::to_time_t( std::chrono::system_clock::now() );
      char buffer[ 32 ]; std::tm local{};
#ifdef _WIN32
      localtime_s( &local, &time );
#else
      localtime_r( &time, &local );
#endif
      std::strftime( buffer, sizeof( buffer ), "%Y%m%d-%H%M%S", &local );
      return std::string( buffer );
    }();

    unsigned passed = 0, failed = 0;
    for( const auto* info : selected )
    {
      log( "=== " + info->name );
      const auto started = std::chrono::steady_clock::now();
      Context ctx( config, server, data, io, options, [ & ]( const std::string& line ) { log( "    " + line ); } );
      bool ok = false;
      try
      {
        auto scenario = info->create();
        scenario->run( ctx );
        ok = true;
      }
      catch( const std::exception& error )
      {
        log( "FAILED " + info->name + ": " + error.what() );
        const auto directory = config.artifacts / runStamp / info->name;
        for( auto& bot : ctx.bots() )
        {
          writeJournal( directory, *bot );
          const auto rows = bot->journal();
          log( "    " + bot->name() + ": last events" );
          const size_t first = rows.size() > 12 ? rows.size() - 12 : 0;
          for( size_t i = first; i < rows.size(); ++i )
            log( "      " + rows[ i ].event + " " + rows[ i ].data.dump().substr( 0, 200 ) );
        }
        if( !ctx.bots().empty() )
          log( "    journals written to " + directory.string() );
      }
      const auto seconds = std::chrono::duration< double >( std::chrono::steady_clock::now() - started ).count();
      if( ok )
      {
        char buffer[ 32 ]; std::snprintf( buffer, sizeof( buffer ), "%.1f", seconds );
        log( "PASSED " + info->name + " (" + buffer + "s)" );
        ++passed;
        if( options.hold && !ctx.bots().empty() )
        {
          log( "bots are standing in the world; press Enter to log them out" );
          std::string line;
          std::getline( std::cin, line );
        }
      }
      else ++failed;
      try { ctx.logoutAll(); } catch( const std::exception& error ) { log( "    cleanup: " + std::string( error.what() ) ); }
    }
    work.reset();
    io.stop();
    thread.join();
    if( !options.keepBots )
      server.purgeBots();
    log( std::to_string( passed ) + " passed, " + std::to_string( failed ) + " failed" );
    return failed ? 1 : 0;
  }
  catch( const std::exception& error )
  {
    std::cerr << "error: " << error.what() << "\n";
    return 1;
  }
}
