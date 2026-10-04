// Login churn, chat, walking and shop events in a loop while sampling the
// world's memory. Every cycle each bot logs in, says a line, walks a short
// segment, opens and closes the gil shop and logs out again; the next cycle
// logs the same characters back in. After each cycle the world process's
// resident memory, the slowest login and shop round trips and any missing
// keepalive replies are logged and appended to log/e2e/soak-<stamp>.log next
// to the server. A world that grows without bound or stops answering events
// shows up in that file.
//
//   sapphire_e2e common.Soak --duration 3600 --bots 3
//
// Without --duration the loop runs exactly one cycle.
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"
#include <chrono>
#include <cstdio>
#include <fstream>
#include <optional>
#include <thread>
#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#include <tlhelp32.h>
#endif

using namespace Sapphire::E2E;

namespace
{
  using Clock = std::chrono::steady_clock;

  double secondsSince( Clock::time_point began )
  {
    return std::chrono::duration< double >( Clock::now() - began ).count();
  }

  std::string fixed( double value, int decimals )
  {
    char buffer[ 32 ];
    std::snprintf( buffer, sizeof( buffer ), "%.*f", decimals, value );
    return buffer;
  }

  std::string stamp( const char* format )
  {
    const auto time = std::chrono::system_clock::to_time_t( std::chrono::system_clock::now() );
    std::tm local{};
#ifdef _WIN32
    localtime_s( &local, &time );
#else
    localtime_r( &time, &local );
#endif
    char buffer[ 32 ];
    std::strftime( buffer, sizeof( buffer ), format, &local );
    return buffer;
  }

#ifdef _WIN32
  bool isUnder( const std::filesystem::path& path, const std::filesystem::path& directory )
  {
    std::error_code ec;
    const auto a = std::filesystem::weakly_canonical( path, ec ), b = std::filesystem::weakly_canonical( directory, ec );
    const auto [ end, unused ] = std::mismatch( b.begin(), b.end(), a.begin(), a.end() );
    return end == b.end();
  }
#endif

  // Resident set size in MiB of the server.exe running from the server
  // directory; several Sapphire stacks can run on one machine.
  std::optional< double > worldMemoryMiB( const std::filesystem::path& serverDir )
  {
    std::optional< double > result;
#ifdef _WIN32
    HANDLE snapshot = CreateToolhelp32Snapshot( TH32CS_SNAPPROCESS, 0 );
    if( snapshot == INVALID_HANDLE_VALUE )
      return result;
    PROCESSENTRY32W entry{};
    entry.dwSize = sizeof( entry );
    for( BOOL more = Process32FirstW( snapshot, &entry ); more && !result; more = Process32NextW( snapshot, &entry ) )
    {
      if( _wcsicmp( entry.szExeFile, L"server.exe" ) != 0 )
        continue;
      HANDLE process = OpenProcess( PROCESS_QUERY_LIMITED_INFORMATION, FALSE, entry.th32ProcessID );
      if( !process )
        continue;
      wchar_t image[ MAX_PATH ];
      DWORD size = MAX_PATH;
      PROCESS_MEMORY_COUNTERS counters{};
      if( QueryFullProcessImageNameW( process, 0, image, &size ) && isUnder( std::filesystem::path( image ).parent_path(), serverDir ) &&
          GetProcessMemoryInfo( process, &counters, sizeof( counters ) ) )
        result = static_cast< double >( counters.WorkingSetSize ) / ( 1024.0 * 1024.0 );
      CloseHandle( process );
    }
    CloseHandle( snapshot );
#else
    (void)serverDir;
#endif
    return result;
  }

  std::string memoryText( const std::optional< double >& mib )
  {
    return mib ? fixed( *mib, 0 ) + " MiB" : std::string( "unknown" );
  }
}

class Soak : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto start = npcPlacement( data, Uldah::Territory, Uldah::StepsOfNaldQuestNpc ).position;
    const auto shop = nearestGilShop( data, Uldah::Territory, start );
    const unsigned botCount = ctx.options().bots ? ctx.options().bots : 3;
    const double duration = ctx.options().duration;
    const auto& serverDir = ctx.config().serverDir;

    CharacterOptions options;
    options.position = shop.route.back();
    std::vector< Fixture > fixtures;
    for( unsigned i = 0; i < botCount; ++i )
      fixtures.push_back( ctx.server().freshCharacter( options ) );
    ctx.log( std::to_string( botCount ) + " bots created at the gil shop; starting memory " + memoryText( worldMemoryMiB( serverDir ) ) );
    std::filesystem::create_directories( ctx.config().artifacts );
    const auto report = ctx.config().artifacts / ( "soak-" + stamp( "%Y%m%d-%H%M%S" ) + ".log" );
    ctx.log( "cycle samples go to " + report.string() );

    const auto started = Clock::now();
    unsigned cycle = 0;
    while( true )
    {
      ++cycle;
      std::vector< Bot* > active;
      double slowestLogin = 0, slowestShop = 0;
      for( size_t i = 0; i < fixtures.size(); ++i )
      {
        auto& bot = ctx.spawn( "soak-" + std::to_string( i ) );
        const auto auth = cycle == 1 ? fixtures[ i ].auth : ctx.server().relogin( fixtures[ i ] );
        auto began = Clock::now();
        const auto state = bot.loginViaLobby( auth, fixtures[ i ].name );
        slowestLogin = std::max( slowestLogin, secondsSince( began ) );
        bot.say( "soak cycle " + std::to_string( cycle ) );
        auto step = Bot::position( state );
        step[ 0 ] += 2.0f;
        bot.walkTo( step );
        bot.walkTo( Bot::position( state ) );
        began = Clock::now();
        bot.openGilShop( shop.shop.layoutId, shop.shop.eventId );
        bot.exitGilShop( shop.shop.eventId );
        slowestShop = std::max( slowestShop, secondsSince( began ) );
        active.push_back( &bot );
      }
      // Keepalives: every bot pings both channels every 3 s; a reply gap shows
      // as sent > replies beyond the two that may still be in flight.
      std::this_thread::sleep_for( std::chrono::seconds( 4 ) );
      uint64_t gaps = 0;
      for( auto* bot : active )
      {
        const auto state = bot->snapshot();
        uint64_t sent = 0;
        for( const auto& [ channel, pings ] : state.at( "heartbeats" ).items() )
          sent += pings.get< uint64_t >();
        const auto replies = state.at( "heartbeat_replies" ).get< uint64_t >();
        gaps += sent > replies + 2 ? sent - replies - 2 : 0;
      }
      const auto line = "cycle " + std::to_string( cycle ) + ": world " + memoryText( worldMemoryMiB( serverDir ) ) +
                        ", slowest login " + fixed( slowestLogin, 1 ) + "s, slowest shop " + fixed( slowestShop, 1 ) +
                        "s, missing keepalive replies " + std::to_string( gaps );
      ctx.log( line );
      std::ofstream( report, std::ios::app ) << stamp( "%Y-%m-%d %H:%M:%S" ) << " elapsed " << fixed( secondsSince( started ), 0 ) << "s " << line << '\n';
      if( duration <= 0 || secondsSince( started ) >= duration )
        break;
      ctx.logoutAll( 35 );
    }
  }
};

EXPOSE_SCENARIO( Soak );
