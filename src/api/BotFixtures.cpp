#include "BotFixtures.h"

#include "SapphireApi.h"
#include "PlayerMinimal.h"

#include <Crypt/Random.h>
#include <Database/DatabaseDef.h>
#include <Logging/Logger.h>

#include <array>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <stdexcept>

using namespace Sapphire::Api;
using Json = nlohmann::json;

namespace
{
  // Starter classes and the public city each one's opening zone mirrors.
  struct StarterClass
  {
    uint8_t classId;
    uint32_t publicTerritory;
  };

  constexpr std::array< StarterClass, 8 > StarterClasses{ {
    { 1, 130 },  // Gladiator   -> Ul'dah, Steps of Nald
    { 2, 130 },  // Pugilist
    { 7, 130 },  // Thaumaturge
    { 3, 129 },  // Marauder    -> Limsa Lominsa, Lower Decks
    { 26, 129 }, // Arcanist
    { 4, 132 },  // Lancer      -> New Gridania
    { 5, 132 },  // Archer
    { 6, 132 },  // Conjurer
  } };

  const StarterClass* findStarter( uint8_t classId )
  {
    for( const auto& entry : StarterClasses )
      if( entry.classId == classId )
        return &entry;
    return nullptr;
  }

  // Alphabetic names keep the lobby/world name handling on its ordinary path.
  std::string randomName()
  {
    const auto token = Sapphire::Common::Util::randomHexToken( 5 );
    std::string letters;
    for( char c : token )
      letters.push_back( static_cast< char >( 'a' + ( std::isdigit( static_cast< unsigned char >( c ) ) ? c - '0' : c - 'a' + 10 ) ) );
    letters[ 0 ] = static_cast< char >( std::toupper( static_cast< unsigned char >( letters[ 0 ] ) ) );
    return "Bot " + letters;
  }

  std::string sqlString( const std::string& value )
  {
    return "'" + g_charaDb.escapeString( value ) + "'";
  }

  std::string sqlFloat( double value )
  {
    if( !std::isfinite( value ) || std::fabs( value ) > 100000.0 )
      throw std::invalid_argument( "position/rotation out of range" );
    char buffer[ 64 ];
    std::snprintf( buffer, sizeof( buffer ), "%.6f", value );
    return buffer;
  }
}

BotFixtures::BotFixtures( SapphireApi& api ) : m_api( api )
{
}

Json BotFixtures::create( const Json& request )
{
  const uint8_t classId = request.value( "class", 1 );
  const auto* starter = findStarter( classId );
  if( !starter )
    throw std::invalid_argument( "class must be a starter class (1,2,3,4,5,6,7,26)" );

  const bool skipOpening = request.value( "skip_opening", true );
  const uint32_t territory = request.value( "territory", skipOpening ? starter->publicTerritory : 0u );
  const int level = request.value( "level", 1 );
  if( level < 1 || level > 50 )
    throw std::invalid_argument( "level must be 1..50" );

  std::array< uint8_t, 26 > appearance{ 1, 0, 1, 50, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 };
  if( request.contains( "appearance" ) )
  {
    const auto& given = request.at( "appearance" );
    if( !given.is_array() || given.size() != appearance.size() )
      throw std::invalid_argument( "appearance must hold 26 bytes" );
    for( size_t i = 0; i < appearance.size(); ++i )
      appearance[ i ] = given.at( i ).get< uint8_t >();
  }

  std::string name = request.value( "name", std::string() );
  if( name.empty() )
  {
    do
      name = randomName();
    while( m_api.checkNameTaken( name ) );
  }
  else if( name.size() > 31 || m_api.checkNameTaken( name ) )
    throw std::invalid_argument( "character name is invalid or already taken" );

  // Account: fresh "bot_" name and a random password the caller receives once.
  const std::string username = std::string( AccountPrefix ) + Common::Util::randomHexToken( 6 );
  const std::string password = Common::Util::randomHexToken( 16 );
  std::string sId;
  if( !m_api.createAccount( username, password, sId ) )
    throw std::runtime_error( "bot account creation failed" );
  const int32_t accountId = m_api.checkSession( sId );
  if( accountId < 0 )
    throw std::runtime_error( "bot account session missing" );

  if( !request.value( "character", true ) )
  {
    // Account only: the caller will create the character through the lobby.
    return { { "result", "success" }, { "username", username }, { "password", password },
             { "account_id", accountId }, { "sId", sId } };
  }

  // Character: identical to lobby creation, but never GM.
  PlayerMinimal player;
  player.setAccountId( static_cast< uint32_t >( accountId ) );
  player.setId( m_api.getNextEntityId() );
  player.setCharacterId( m_api.getNextCharaId() );
  player.setName( name.c_str() );
  for( uint8_t i = 0; i < appearance.size(); ++i )
    player.setLook( i, appearance[ i ] );
  player.setVoice( 1 );
  player.setGuardianDeity( 1 );
  player.setBirthDay( 1, 1 );
  player.setClass( classId );
  player.setTribe( 1 );
  player.setGmRank( 0 );
  player.saveAsNew();

  const auto characterId = std::to_string( player.getCharacterId() );

  // Template: the same adjustments the old fixture runner made with raw SQL.
  std::string update = "UPDATE charainfo SET GMRank = 0";
  if( skipOpening )
    update += ", IsNewGame = 0, OpeningSequence = 2";
  if( territory != 0 )
    update += ", TerritoryType = " + std::to_string( territory ) + ", TerritoryId = 0";
  if( request.contains( "position" ) )
  {
    const auto& pos = request.at( "position" );
    if( !pos.is_array() || pos.size() != 3 )
      throw std::invalid_argument( "position must be [x, y, z]" );
    update += ", PosX = " + sqlFloat( pos.at( 0 ).get< double >() ) +
              ", PosY = " + sqlFloat( pos.at( 1 ).get< double >() ) +
              ", PosZ = " + sqlFloat( pos.at( 2 ).get< double >() );
  }
  if( request.contains( "rotation" ) )
    update += ", PosR = " + sqlFloat( request.at( "rotation" ).get< double >() );
  update += " WHERE CharacterId = " + characterId + ";";
  g_charaDb.directExecute( update );

  if( level != 1 )
    g_charaDb.directExecute( "UPDATE characlass SET Lvl = " + std::to_string( level ) +
                             ", Exp = 0 WHERE CharacterId = " + characterId + ";" );

  Logger::info( "Created bot {0} / {1} (character {2})", username, name, characterId );

  return {
    { "result", "success" },
    { "username", username },
    { "password", password },
    { "name", name },
    { "account_id", accountId },
    { "character_id", player.getCharacterId() },
    { "entity_id", player.getId() },
    { "sId", sId },
  };
}

Json BotFixtures::list()
{
  Json accounts = Json::array();
  auto res = g_charaDb.query(
    "SELECT a.account_id, a.account_name, c.CharacterId, c.Name, c.Online "
    "FROM accounts a LEFT JOIN charainfo c ON c.AccountId = a.account_id "
    "WHERE a.account_name LIKE " + sqlString( std::string( AccountPrefix ) + "%" ) +
    " ORDER BY a.account_id, c.CharacterId;" );

  Json* current = nullptr;
  uint32_t currentId = 0;
  while( res && res->next() )
  {
    const auto accountId = res->getUInt( 1 );
    if( !current || currentId != accountId )
    {
      accounts.push_back( { { "account_id", accountId },
                            { "username", res->getString( 2 ) },
                            { "characters", Json::array() } } );
      current = &accounts.back();
      currentId = accountId;
    }
    if( !res->isNull( 3 ) )
      ( *current )[ "characters" ].push_back( { { "character_id", res->getUInt64( 3 ) },
                                                { "name", res->getString( 4 ) },
                                                { "online", res->getBoolean( 5 ) } } );
  }
  return { { "result", "success" }, { "accounts", accounts } };
}

Json BotFixtures::purge()
{
  const auto listing = list();
  uint32_t deletedAccounts = 0, deletedCharacters = 0;
  Json skipped = Json::array();

  for( const auto& account : listing.at( "accounts" ) )
  {
    bool online = false;
    for( const auto& character : account.at( "characters" ) )
      if( character.at( "online" ).get< bool >() )
      {
        online = true;
        skipped.push_back( character.at( "name" ) );
      }
    if( online )
      continue;

    for( const auto& character : account.at( "characters" ) )
    {
      m_api.deleteCharacterById( character.at( "character_id" ).get< uint64_t >() );
      ++deletedCharacters;
    }
    const auto accountId = account.at( "account_id" ).get< uint32_t >();
    g_charaDb.directExecute( "DELETE FROM accounts WHERE account_id = " + std::to_string( accountId ) + ";" );
    m_api.removeSessionsForAccount( accountId );
    ++deletedAccounts;
  }

  Logger::info( "Purged {0} bot accounts / {1} characters, skipped {2} online", deletedAccounts,
                deletedCharacters, skipped.size() );
  return { { "result", "success" },
           { "deleted_accounts", deletedAccounts },
           { "deleted_characters", deletedCharacters },
           { "skipped_online", skipped } };
}
