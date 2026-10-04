#pragma once
// What a running scenario has at hand: the development server's API, the game
// data, a logger and the bots it spawns. Bots created through the context are
// logged out and cleaned up by the runner when the scenario ends.
#include "Config.h"
#include "GameData.h"
#include "Server.h"
#include "../client/Bot.h"
#include <asio.hpp>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace Sapphire::E2E
{
  struct Options
  {
    bool hold = false;       // keep the bots in the world after the scenario until Enter
    bool keepBots = false;   // do not purge bot_ accounts before and after the run
    double duration = 0;     // long-running scenarios (soak): seconds to keep going
    unsigned bots = 0;       // long-running scenarios: bot count (0 = scenario default)
  };

  class Context
  {
  public:
    Context( const Config& config, Server& server, GameData& data, asio::io_service& io, const Options& options,
             std::function< void( const std::string& ) > log );

    const Config& config() const { return m_config; }
    Server& server() { return m_server; }
    GameData& data() { return m_data; }
    const Options& options() const { return m_options; }
    void log( const std::string& line ) { m_log( line ); }

    // A new bot (not yet connected). The name shows up in logs and journals.
    Bot& spawn( const std::string& name );
    // Create a character and log the bot in; the usual way a scenario starts.
    Bot& spawnCharacter( const std::string& name, const CharacterOptions& options = {} );
    const Fixture& fixture( const Bot& bot ) const;
    std::vector< std::unique_ptr< Bot > >& bots() { return m_bots; }
    // Log out every bot that is still in the world (parallel), then drop them.
    void logoutAll( double timeout = 35 );

  private:
    const Config& m_config;
    Server& m_server;
    GameData& m_data;
    asio::io_service& m_io;
    const Options& m_options;
    std::function< void( const std::string& ) > m_log;
    std::vector< std::unique_ptr< Bot > > m_bots;
    std::map< const Bot*, Fixture > m_fixtures;
  };
}
