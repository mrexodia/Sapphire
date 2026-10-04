#pragma once
// Where the development stack is and how to reach it, read from the server's
// own config files next to the runner (bin/config/*.ini). Nothing here is a
// test-specific config file: the API address comes from global.ini's RestHost
// and RestPort, the secret from ServerSecret, the game data from DataPath and
// the navmeshes from world.ini's MeshPath.
#include <cstdint>
#include <filesystem>
#include <string>

namespace Sapphire::E2E
{
  struct Config
  {
    std::filesystem::path serverDir;   // the directory server.exe runs from (bin/)
    std::filesystem::path configDir;   // serverDir/config
    std::string apiHost;
    uint16_t apiPort = 80;
    std::string secret;
    std::filesystem::path dataPath;    // game/sqpack
    std::filesystem::path meshPath;    // navmesh root the world uses
    std::filesystem::path artifacts;   // journals of failed scenarios

    // Overrides are empty/zero when not given on the command line.
    static Config load( const std::filesystem::path& serverDir, const std::string& apiOverride,
                        const std::string& secretOverride );
  };
}
