#include "Config.h"
#include <Config/ConfigMgr.h>
#include <Config/ConfigDef.h>
#include <stdexcept>

namespace Sapphire::E2E
{
  Config Config::load( const std::filesystem::path& serverDir, const std::string& apiOverride,
                       const std::string& secretOverride )
  {
    Config config;
    config.serverDir = std::filesystem::absolute( serverDir );
    config.configDir = config.serverDir / "config";
    if( !std::filesystem::is_directory( config.configDir ) )
      throw std::runtime_error( "no config directory at " + config.configDir.string() +
                                "; run from the server's bin directory or pass --server-dir" );

    Common::ConfigMgr configMgr( config.configDir );
    Common::Config::GlobalConfig global{};
    if( !configMgr.loadGlobalConfig( global ) )
      throw std::runtime_error( "cannot read " + ( config.configDir / "global.ini" ).string() );
    config.apiHost = global.network.restHost;
    config.apiPort = global.network.restPort;
    config.secret = global.general.serverSecret;
    config.dataPath = global.general.dataPath;

    if( !configMgr.loadConfig( "world.ini" ) )
      throw std::runtime_error( "cannot read " + ( config.configDir / "world.ini" ).string() );
    std::filesystem::path meshPath = configMgr.getValue< std::string >( "Navigation", "MeshPath", "navi" );
    config.meshPath = meshPath.is_absolute() ? meshPath : config.serverDir / meshPath;
    config.artifacts = config.serverDir / "log" / "e2e";

    if( !apiOverride.empty() )
    {
      const auto colon = apiOverride.rfind( ':' );
      if( colon == std::string::npos )
        throw std::runtime_error( "--api expects host:port" );
      config.apiHost = apiOverride.substr( 0, colon );
      config.apiPort = static_cast< uint16_t >( std::stoul( apiOverride.substr( colon + 1 ) ) );
    }
    if( !secretOverride.empty() )
      config.secret = secretOverride;
    return config;
  }
}
