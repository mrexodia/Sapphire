#include "SapphireApi.h"
#include <Crypt/base64.h>
#include <Crypt/Random.h>
#include "Session.h"
#include "PlayerMinimal.h"
#include <time.h>

#include <sstream>

#include <nlohmann/json.hpp>

#include <Database/DatabaseDef.h>

using namespace Sapphire::Api;

bool SapphireApi::login( const std::string& username, const std::string& pass, std::string& sId )
{
  auto stmt = g_charaDb.getPreparedStatement( Db::ZoneDbStatements::ACCOUNT_SEL_BY_NAME_PASS );
  stmt->setString( 1, username );
  stmt->setString( 2, pass );

  // check if a user with that name / password exists
  auto pQR = g_charaDb.query( stmt );
  // found?
  if( !pQR || !pQR->next() )
    return false;

  // user found, proceed
  uint32_t accountId = pQR->getUInt( 1 );

  // Preserve the 62-character wire format, without process-global/time-seeded RNG state.
  // Independent logins must not replace another account's live session.
  std::string sessionId;
  do
  {
    sessionId = Common::Util::randomHexToken( 31 );
  }
  while( m_sessionMap.find( sessionId ) != m_sessionMap.end() );

  // create session for the new sessionid and store to sessionlist
  auto pSession = std::make_shared< Session >();
  pSession->setAccountId( accountId );
  pSession->setSessionId( sessionId.c_str() );

  m_sessionMap[ sessionId ] = pSession;
  sId = sessionId;

  return true;
}


bool SapphireApi::insertSession( const uint32_t accountId, std::string& sId )
{
  // create session for the new sessionid and store to sessionlist
  auto pSession = std::make_shared< Session >();
  pSession->setAccountId( accountId );
  pSession->setSessionId( sId.c_str() );

  m_sessionMap[ sId ] = pSession;

  return true;
}

bool SapphireApi::createAccount( const std::string& username, const std::string& pass, std::string& sId )
{
  // get account from login name
  auto stmt = g_charaDb.getPreparedStatement( Db::ZoneDbStatements::ACCOUNT_SEL_BY_NAME );
  stmt->setString( 1, username );

  auto pQR = g_charaDb.query( stmt );
  // found?
  if( pQR && pQR->next() )
    return false;

  // we are clear and can create a new account
  // get the next free account id
  auto stmtMaxId = g_charaDb.getPreparedStatement( Db::ZoneDbStatements::ACCOUNT_SEL_MAX_ID );
  pQR = g_charaDb.query( stmtMaxId );
  if( !pQR || !pQR->next() )
    return false;
  uint32_t accountId = pQR->getUInt( 1 ) + 1;

  auto stmtInsert = g_charaDb.getPreparedStatement( Db::ZoneDbStatements::ACCOUNT_INS );
  stmtInsert->setUInt( 1, accountId );
  stmtInsert->setString( 2, username );
  stmtInsert->setString( 3, pass );
  stmtInsert->setUInt( 4, static_cast< uint32_t >( time( nullptr ) ) );

  // store the account to the db
  g_charaDb.directExecute( stmtInsert );


  if( !login( username, pass, sId ) )
    return false;

  return true;
}

int SapphireApi::createCharacter( const uint32_t accountId, const std::string& name,
                                  const std::string& infoJson,
                                  const uint32_t gmRank )
{
  Api::PlayerMinimal newPlayer;

  newPlayer.setAccountId( accountId );
  newPlayer.setId( getNextEntityId() );
  newPlayer.setCharacterId( getNextCharaId() );
  newPlayer.setName( name.c_str() );

  auto json = nlohmann::json::parse( infoJson );

  const char* ptr = infoJson.c_str() + 50;

  std::string lookPart( ptr );
  auto pos = lookPart.find_first_of( "]" );
  if( pos != std::string::npos )
  {
    lookPart = lookPart.substr( 0, pos + 1 );
  }

  std::vector< int32_t > tmpVector;
  std::vector< int32_t > tmpVector2;

  for( auto& v : json[ "content" ] )
  {
    if( v.is_array() )
    {
      for( auto& vs : v )
      {
        tmpVector.push_back( std::stoi( std::string( vs ) ) );
      }
    }

    if( !v.empty() && !v.is_array() )
      tmpVector2.push_back( std::stoi( std::string( v ) ) );
  }

  // leaving this in for now for reference
  // BOOST_FOREACH( boost::property_tree::ptree::value_type& v, pt.get_child( "content" ) )
  //       {
  //         boost::property_tree::ptree subtree1 = v.second;
  //         BOOST_FOREACH( boost::property_tree::ptree::value_type& vs, subtree1 )
  //               {
  //                 boost::property_tree::ptree subtree2 = vs.second;
  //                 //std::cout << vs.second.data();
  //                 tmpVector.push_back( std::stoi( vs.second.data() ) );
  //               }
  //         if( !v.second.data().empty() )
  //           tmpVector2.push_back( std::stoi( v.second.data() ) );
  //       }

  std::vector< int32_t >::iterator it = tmpVector.begin();
  for( int32_t i = 0; it != tmpVector.end(); ++it, i++ )
  {
    newPlayer.setLook( i, *it );
  }

  std::string rest = infoJson.substr( pos + 53 );

  newPlayer.setVoice( tmpVector2.at( 0 ) );
  newPlayer.setGuardianDeity( tmpVector2.at( 1 ) );
  newPlayer.setBirthDay( tmpVector2.at( 3 ), tmpVector2.at( 2 ) );
  newPlayer.setClass( tmpVector2.at( 4 ) );
  newPlayer.setTribe( tmpVector2.at( 5 ) );
  newPlayer.setGmRank( gmRank );

  newPlayer.saveAsNew();

  return newPlayer.getAccountId();
}

void SapphireApi::deleteCharacter( std::string name, const uint32_t accountId )
{
  auto charList = getCharList( accountId );
  for( auto& tmpPlayer : charList )
  {
    if( tmpPlayer.getName() == name )
    {
      deleteCharacterById( tmpPlayer.getCharacterId() );
      return;
    }
  }
}

void SapphireApi::deleteCharacterById( uint64_t characterId )
{
  const auto id = std::to_string( characterId );
  for( const char* table : { "charainfo", "characlass", "charaglobalitem", "charainfoblacklist",
                             "charainfofriendlist", "charainfolinkshell", "charainfosearch",
                             "charaitemcrystal", "charaiteminventory", "charaitemgearset", "charaquest",
                             "charainfoachievement", "charaitemcurrency", "charamonsternote" } )
  {
    g_charaDb.execute( "DELETE FROM " + std::string( table ) + " WHERE CharacterId = " + id + ";" );
  }
}

std::vector< PlayerMinimal > SapphireApi::getCharList( uint32_t accountId )
{

  std::vector< Api::PlayerMinimal > charList;

  auto stmt = g_charaDb.getPreparedStatement( Db::ZoneDbStatements::CHARA_SEL_BY_ACCOUNT_ID );
  stmt->setUInt( 1, accountId );

  auto pQR = g_charaDb.query( stmt );
  if( !pQR )
    return charList;

  while( pQR->next() )
  {
    Api::PlayerMinimal player;

    auto charId = pQR->getUInt64( 1 );

    player.load( charId );

    charList.push_back( player );
  }
  return charList;
}

bool SapphireApi::checkNameTaken( std::string_view name )
{
  auto stmt = g_charaDb.getPreparedStatement( Db::ZoneDbStatements::CHARA_SEL_BY_NAME );
  stmt->setString( 1, std::string( name ) );

  auto pQR = g_charaDb.query( stmt );

  if( !pQR || !pQR->next() )
    return false;
  else
    return true;
}

uint32_t SapphireApi::getNextEntityId()
{
  uint32_t charId = 0;

  auto pQR = g_charaDb.query( "SELECT MAX(EntityId) FROM charainfo" );

  if( !pQR || !pQR->next() )
    return 0x00200001;

  charId = pQR->getUInt( 1 ) + 1;
  if( charId < 0x00200001 )
    return 0x00200001;

  return charId;
}

uint64_t SapphireApi::getNextCharaId()
{
  uint64_t contentId = 0;

  auto pQR = g_charaDb.query( "SELECT MAX(CharacterId) FROM charainfo" );

  if( !pQR || !pQR->next() )
    return 0x0040000001000001;

  contentId = pQR->getUInt64( 1 ) + 1;
  if( contentId < 0x0040000001000001 )
    return 0x0040000001000001;

  return contentId;
}

int SapphireApi::checkSession( const std::string& sId )
{
  auto it = m_sessionMap.find( sId );

  if( it == m_sessionMap.end() )
    return -1;

  return it->second->getAccountId();
}


bool SapphireApi::removeSession( const std::string& sId )
{
  auto it = m_sessionMap.find( sId );

  if( it != m_sessionMap.end() )
    m_sessionMap.erase( sId );

  return true;
}

void SapphireApi::removeSessionsForAccount( uint32_t accountId )
{
  for( auto it = m_sessionMap.begin(); it != m_sessionMap.end(); )
  {
    if( it->second && it->second->getAccountId() == accountId )
      it = m_sessionMap.erase( it );
    else
      ++it;
  }
}

std::string SapphireApi::getAccountName( uint32_t accountId )
{
  auto res = g_charaDb.query( "SELECT account_name FROM accounts WHERE account_id = " + std::to_string( accountId ) + ";" );
  if( !res || !res->next() )
    return {};
  return res->getString( 1 );
}
