#pragma once

#include <nlohmann/json.hpp>

namespace Sapphire::Api
{
  class SapphireApi;

  /// Development-only fixtures for headless test bots.
  ///
  /// Bot accounts are ordinary accounts whose name starts with "bot_". Their
  /// characters are ordinary non-GM characters. Nothing here is reachable
  /// unless api.ini enables [Development] BotApi and the caller presents the
  /// server secret, so this is strictly a local development convenience.
  class BotFixtures
  {
  public:
    static constexpr const char* AccountPrefix = "bot_";

    explicit BotFixtures( SapphireApi& api );

    /// Create a fresh bot account with one character in the requested state.
    ///
    /// Request fields (all optional):
    ///   name          character name; default "Bot <random>"
    ///   class         starter class id (1 GLA, 2 PGL, 3 MRD, 4 LNC, 5 ARC, 6 CNJ, 7 THM, 26 ACN); default 1
    ///   territory     territory type the character starts in; default is the
    ///                 public city matching the class when skip_opening is set
    ///   position      [x, y, z]; default is the class' creation position
    ///   rotation      radians; default 0
    ///   level         class level 1..50; default 1
    ///   skip_opening  mark the opening sequence done; default true
    ///   appearance    26 customize bytes; default is a fixed Hyur Midlander
    ///   character     false creates the account only, for lobby creation tests; default true
    ///
    /// Returns {username, password, name, character_id, entity_id, sId}.
    nlohmann::json create( const nlohmann::json& request );

    /// List every bot account with its characters and the world's online marker.
    nlohmann::json list();

    /// Delete every bot account whose characters are all offline.
    /// Returns {deleted_accounts, deleted_characters, skipped_online: [names]}.
    nlohmann::json purge();

  private:
    SapphireApi& m_api;
  };
}
