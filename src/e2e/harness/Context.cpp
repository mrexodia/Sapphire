#include "Context.h"
#include <future>

namespace Sapphire::E2E
{
  Context::Context( const Config& config, Server& server, GameData& data, asio::io_service& io, const Options& options,
                    std::function< void( const std::string& ) > log ) :
    m_config( config ), m_server( server ), m_data( data ), m_io( io ), m_options( options ), m_log( std::move( log ) )
  {
  }

  Bot& Context::spawn( const std::string& name )
  {
    for( const auto& bot : m_bots )
      if( bot->name() == name )
        throw std::logic_error( "a bot named " + name + " already exists in this scenario" );
    m_bots.push_back( std::make_unique< Bot >( m_io, name ) );
    return *m_bots.back();
  }

  Bot& Context::spawnCharacter( const std::string& name, const CharacterOptions& options )
  {
    auto fixture = m_server.freshCharacter( options );
    auto& bot = spawn( name );
    m_fixtures[ &bot ] = fixture;
    const auto state = bot.loginViaLobby( fixture.auth, fixture.name );
    const auto position = Bot::position( state );
    log( name + ": " + fixture.name + " is in territory " + std::to_string( state.at( "territory" ).get< int >() ) +
         " at " + std::to_string( position[ 0 ] ).substr( 0, 6 ) + ", " + std::to_string( position[ 1 ] ).substr( 0, 6 ) +
         ", " + std::to_string( position[ 2 ] ).substr( 0, 6 ) );
    return bot;
  }

  const Fixture& Context::fixture( const Bot& bot ) const
  {
    auto it = m_fixtures.find( &bot );
    if( it == m_fixtures.end() )
      throw std::logic_error( bot.name() + " was not created through spawnCharacter" );
    return it->second;
  }

  void Context::logoutAll( double timeout )
  {
    std::vector< std::future< void > > pending;
    for( auto& bot : m_bots )
    {
      Bot* raw = bot.get();
      pending.push_back( std::async( std::launch::async, [ raw, timeout ] {
        try
        {
          const auto state = raw->snapshot();
          if( state.at( "phase" ) == "ready" )
            raw->logout( timeout );
        }
        catch( const std::exception& )
        {
          // A bot that already failed or disconnected has nothing to log out.
        }
        raw->close();
      } ) );
    }
    for( auto& future : pending )
      future.wait();
    m_bots.clear();
    m_fixtures.clear();
  }
}
