#pragma once
// The development server's HTTP API: the lobby login routes every client uses
// and the bot fixture routes (/sapphire-api/dev/*) that create and purge
// throwaway bot_ accounts and characters.
#include <array>
#include <cstdint>
#include <nlohmann/json.hpp>
#include <optional>
#include <string>
#include <vector>

namespace Sapphire::E2E
{
  using Json = nlohmann::json;
  using Point = std::array< float, 3 >;

  struct Auth
  {
    std::string sessionId;
    std::string lobbyHost;
    uint16_t lobbyPort = 0;
  };

  // A bot account with one character, created past the opening and ready to log in.
  struct Fixture
  {
    std::string name;      // character name
    std::string username;
    std::string password;
    uint64_t characterId = 0;
    uint32_t entityId = 0;
    Auth auth;             // a login made right after creation
  };

  // A bot account without a character, for lobby character-creation scenarios.
  struct Account
  {
    std::string username;
    std::string password;
    std::string name;      // the character name the scenario should create
    Auth auth;
  };

  struct CharacterOptions
  {
    std::optional< Point > position;
    uint16_t territory = 130;  // Ul'dah, Steps of Nald
    uint8_t classJob = 1;      // Gladiator
    uint8_t level = 1;
  };

  struct BotCharacter
  {
    std::string name;
    bool online = false;
  };

  struct BotAccount
  {
    std::string username;
    std::vector< BotCharacter > characters;
  };

  struct ApiError : std::runtime_error { using std::runtime_error::runtime_error; };

  class Server
  {
  public:
    Server( std::string host, uint16_t port, std::string secret );

    // POST a JSON body; throws ApiError unless the status is `expected`.
    Json post( const std::string& path, const Json& body, int expected = 200 );
    // The lobby login route, returning the raw status for negative tests.
    int tryLogin( const std::string& username, const std::string& password, Json& reply );

    void checkAlive();
    Fixture freshCharacter( const CharacterOptions& options = {} );
    Account freshAccount();
    Auth login( const std::string& username, const std::string& password );
    Auth login( const Fixture& fixture ) { return login( fixture.username, fixture.password ); }
    Auth login( const Account& account ) { return login( account.username, account.password ); }
    // Wait until the world dropped the character's session, then log in again.
    Auth relogin( const Fixture& fixture, double timeoutSeconds = 30 );
    Auth relogin( const Account& account, double timeoutSeconds = 30 );
    void waitOffline( const std::string& characterName, double timeoutSeconds = 30 );
    std::vector< BotAccount > listBots();
    Json purgeBots();

    const std::string& host() const { return m_host; }
    uint16_t port() const { return m_port; }

  private:
    std::string m_host;
    uint16_t m_port;
    std::string m_secret;
  };
}
