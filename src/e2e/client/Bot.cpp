#include "Bot.h"
#include "../harness/Server.h"
#include "../harness/Scenario.h"
#include <algorithm>
#include <cmath>
#include <future>

namespace Sapphire::E2E
{
  using Testing::Client;
  using Testing::ProtocolError;

  static double dist( const Point& a, const Point& b )
  {
    return std::sqrt( std::pow( a[ 0 ] - b[ 0 ], 2 ) + std::pow( a[ 1 ] - b[ 1 ], 2 ) + std::pow( a[ 2 ] - b[ 2 ], 2 ) );
  }

  static std::string excerpt( const Json& state )
  {
    Json brief{ { "phase", state.value( "phase", Json() ) }, { "territory", state.value( "territory", Json() ) },
                { "event_id", state.value( "event_id", Json() ) }, { "scene", state.value( "scene", Json() ) },
                { "moving", state.value( "moving", Json() ) }, { "party", state.value( "party", Json() ) } };
    if( state.contains( "observed_position" ) ) brief[ "observed_position" ] = state[ "observed_position" ];
    if( state.contains( "actors" ) ) brief[ "actors" ] = state[ "actors" ].size();
    if( state.contains( "error" ) ) brief[ "error" ] = state[ "error" ];
    return brief.dump();
  }

  Bot::Bot( asio::io_service& io, std::string name ) : m_io( io ), m_name( std::move( name ) )
  {
    // The client is created on the Asio thread so every handler runs there.
    std::promise< std::shared_ptr< Client > > created;
    m_io.post( [ & ] {
      created.set_value( std::make_shared< Client >( m_io, m_name, [ this ]( const Json& event ) { onEvent( event ); } ) );
    } );
    m_client = created.get_future().get();
  }

  Bot::~Bot()
  {
    try { close(); } catch( ... ) {}
  }

  template< class F >
  auto Bot::call( F&& function ) -> decltype( function() )
  {
    using Result = decltype( function() );
    std::promise< Result > promise;
    auto future = promise.get_future();
    m_io.post( [ &promise, &function ] {
      try
      {
        if constexpr( std::is_void_v< Result > ) { function(); promise.set_value(); }
        else promise.set_value( function() );
      }
      catch( ... ) { promise.set_exception( std::current_exception() ); }
    } );
    return future.get();
  }

  void Bot::onEvent( const Json& event )
  {
    // Called on the Asio thread for every journal event the client emits.
    std::lock_guard< std::mutex > lock( m_mutex );
    m_journal.push_back( { std::chrono::steady_clock::now(), event.at( "event" ).get< std::string >(), event.value( "data", Json::object() ) } );
    if( m_journal.size() > 4096 ) m_journal.pop_front();
    if( m_journal.back().event == "failure" )
      m_failure = m_journal.back().data.value( "reason", "bot failed" );
    if( m_journal.back().event != "packet" )
    {
      ++m_version;
      m_changed.notify_all();
    }
  }

  Json Bot::snapshot()
  {
    auto client = m_client;
    return call( [ client ] { return client->snapshot(); } );
  }

  std::vector< JournalEntry > Bot::journal( std::chrono::steady_clock::time_point since )
  {
    std::lock_guard< std::mutex > lock( m_mutex );
    std::vector< JournalEntry > rows;
    for( const auto& row : m_journal )
      if( row.at > since )
        rows.push_back( row );
    return rows;
  }

  Json Bot::waitState( const Predicate& predicate, const std::string& description, Seconds timeout )
  {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::duration_cast< std::chrono::steady_clock::duration >( std::chrono::duration< double >( timeout ) );
    while( true )
    {
      uint64_t version;
      {
        std::lock_guard< std::mutex > lock( m_mutex );
        version = m_version;
      }
      auto state = snapshot();
      if( state.value( "phase", "" ) == "failed" )
        throw ProtocolError( m_name + ": " + state.value( "error", std::string( "bot failed" ) ) );
      if( predicate( state ) )
        return state;
      std::unique_lock< std::mutex > lock( m_mutex );
      if( !m_changed.wait_until( lock, deadline, [ & ] { return m_version != version || !m_failure.empty(); } ) )
        throw Timeout( m_name + ": timeout waiting for " + description + "; state=" + excerpt( state ) );
      if( !m_failure.empty() )
        throw ProtocolError( m_name + ": " + m_failure );
    }
  }

  const Json* Bot::actor( const Json& s, uint32_t id )
  {
    const auto& actors = s.at( "actors" );
    auto it = actors.find( std::to_string( id ) );
    return it == actors.end() ? nullptr : &*it;
  }

  std::optional< Scene > Bot::scene( const Json& s )
  {
    const auto& scene = s.at( "scene" );
    if( scene.is_null() ) return std::nullopt;
    return Scene{ scene.at( "event_id" ).get< uint32_t >(), scene.at( "scene_id" ).get< uint32_t >(), scene.at( "token" ).get< uint64_t >() };
  }

  uint32_t Bot::gil( const Json& s )
  {
    const auto& inventory = s.at( "rewards" ).at( "inventory" );
    auto it = inventory.find( "2000:0" );
    return it == inventory.end() ? 0 : it->at( "count" ).get< uint32_t >();
  }

  std::string Bot::emptyBagSlot( const Json& inventory )
  {
    for( uint32_t bag = 0; bag < 4; ++bag )
      for( uint32_t slot = 0; slot < 25; ++slot )
        if( !inventory.contains( slotKey( bag, slot ) ) )
          return slotKey( bag, slot );
    throw Failure( "no empty ordinary bag slot" );
  }

  // -- lobby ------------------------------------------------------------------

  Json Bot::waitLobbyPhase( const LoginOptions& options, const std::string& phase, const std::string& description, Seconds timeout )
  {
    auto client = m_client;
    call( [ client, options ] { client->login( options ); } );
    return waitState( [ & ]( const Json& s ) { return s.at( "phase" ) == phase; }, description, timeout );
  }

  static LoginOptions loginOptions( const Auth& auth, const std::string& character, double timeout )
  {
    LoginOptions options;
    options.host = auth.lobbyHost;
    options.port = auth.lobbyPort;
    options.session = auth.sessionId;
    options.character = character;
    options.timeoutSeconds = static_cast< int >( std::min( 120.0, std::max( 1.0, timeout ) ) );
    return options;
  }

  Json Bot::waitWorldReady( Seconds timeout )
  {
    auto state = waitState( [ & ]( const Json& s ) { return s.at( "phase" ) == "ready"; }, "world ready", timeout );
    if( state.at( "gm_rank" ) != 0 )
      throw Failure( m_name + ": scenarios require a non-GM character" );
    return state;
  }

  Json Bot::loginViaLobby( const Auth& auth, const std::string& character, Seconds timeout )
  {
    auto options = loginOptions( auth, character, timeout );
    auto client = m_client;
    call( [ client, options ] { client->login( options ); } );
    return waitWorldReady( timeout );
  }

  Json Bot::createCharacterViaLobby( const Auth& auth, const std::string& character, uint8_t creationClass, Seconds timeout )
  {
    if( creationClass != 1 && creationClass != 2 && creationClass != 7 )
      throw Failure( "unsupported Ul'dah starting class" );
    auto options = loginOptions( auth, character, timeout );
    options.createCharacter = true;
    options.creationClass = creationClass;
    auto client = m_client;
    call( [ client, options ] { client->login( options ); } );
    auto state = waitWorldReady( timeout );
    if( state.value( "created_via_lobby", false ) != true )
      throw Failure( "character creation was not confirmed by the refreshed lobby list" );
    return state;
  }

  Json Bot::deleteCharacterViaLobby( const Auth& auth, const std::string& character, Seconds timeout )
  {
    auto options = loginOptions( auth, character, timeout );
    options.deleteCharacter = true;
    auto state = waitLobbyPhase( options, "lobby_deleted", "refreshed lobby deletion", timeout );
    if( state.value( "deleted_via_lobby", false ) != true || !state.at( "characters" ).empty() )
      throw Failure( "character deletion was not confirmed by the refreshed lobby list" );
    return state;
  }

  Json Bot::expectNameRejected( const Auth& auth, const std::string& character, Seconds timeout )
  {
    auto options = loginOptions( auth, character, timeout );
    options.expectNameRejected = true;
    auto state = waitLobbyPhase( options, "name_rejected", "exact duplicate-name rejection", timeout );
    if( state.at( "name_rejection" ) != Json{ { "error_code", 3074 }, { "error_status", 0 }, { "message_number", 13004 } } )
      throw Failure( "unexpected duplicate-name rejection identity" );
    return state;
  }

  Json Bot::expectCharacterAbsent( const Auth& auth, const std::string& character, Seconds timeout )
  {
    auto options = loginOptions( auth, character, timeout );
    options.expectCharacterAbsent = true;
    return waitLobbyPhase( options, "character_absent", "fresh lobby character absence", timeout );
  }

  void Bot::logout( Seconds timeout, bool waitServerClose )
  {
    auto client = m_client;
    call( [ client ] { client->logout(); } );
    waitState( [ & ]( const Json& s ) { return s.at( "phase" ) == "logged_out" || s.at( "phase" ) == "logout_complete"; },
               "logout acknowledgement", timeout );
    if( waitServerClose )
      waitState( [ & ]( const Json& s ) { return s.at( "phase" ) == "logout_complete"; }, "server logout connection close", timeout );
    close();
  }

  void Bot::close()
  {
    auto client = m_client;
    call( [ client ] { client->close(); } );
  }

  // -- movement and chat ------------------------------------------------------

  Json Bot::walkTo( const Point& position, float speed, Seconds timeout )
  {
    auto client = m_client;
    call( [ client, position, speed ] { client->walkTo( position, speed ); } );
    return waitState( [ & ]( const Json& s ) { return !s.at( "moving" ).get< bool >(); }, "waypoint sent", timeout );
  }

  void Bot::walkRoute( const std::vector< Point >& waypoints, float speed, Seconds timeout )
  {
    if( waypoints.empty() || waypoints.size() > 2048 )
      throw Failure( "route must contain 1..2048 waypoints" );
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::duration< double >( timeout );
    for( const auto& point : waypoints )
    {
      const auto remaining = std::chrono::duration< double >( deadline - std::chrono::steady_clock::now() ).count();
      if( remaining <= 0 )
        throw Timeout( m_name + ": route deadline exceeded" );
      walkTo( point, speed, remaining );
    }
  }

  void Bot::say( const std::string& message )
  {
    auto client = m_client;
    call( [ client, message ] { client->say( message ); } );
  }

  Json Bot::expectSay( uint32_t actor, const std::string& message, Seconds timeout )
  {
    return waitState( [ & ]( const Json& s ) {
      for( const auto& row : s.at( "chat" ) )
        if( row.at( "actor" ) == actor && row.at( "message" ) == message ) return true;
      return false;
    }, "say received from expected actor", timeout );
  }

  void Bot::tell( uint32_t target, const std::string& name, const std::string& message )
  {
    auto client = m_client;
    call( [ = ] { client->tell( target, name, message ); } );
  }

  void Bot::tellRemote( uint32_t target, const std::string& name, const std::string& message )
  {
    auto client = m_client;
    call( [ = ] { client->tellRemote( target, name, message ); } );
  }

  void Bot::tellVisible( uint32_t target, const std::string& name, const std::string& message )
  {
    auto client = m_client;
    call( [ = ] { client->tellVisible( target, name, message ); } );
  }

  Json Bot::tellOffline( uint32_t target, const std::string& name, const std::string& message, Seconds timeout )
  {
    auto client = m_client;
    call( [ = ] { client->tell( target, name, message, true ); } );
    return waitState( [ & ]( const Json& s ) { return s.at( "tell_not_found" ) == Json{ { "name", name } }; },
                      "exact unavailable Tell target result", timeout ).at( "tell_not_found" );
  }

  Json Bot::expectTell( const Json& senderState, const std::string& message, Seconds timeout )
  {
    const auto expectedEntity = entity( senderState );
    const auto expectedName = senderState.at( "actors" ).at( std::to_string( expectedEntity ) ).at( "name" ).get< std::string >();
    std::vector< uint64_t > identities;
    for( const auto& row : senderState.at( "characters" ) )
      if( row.at( "entity_id" ) == expectedEntity && row.at( "name" ) == expectedName )
        identities.push_back( row.at( "character_id" ).get< uint64_t >() );
    if( identities.size() != 1 )
      throw Failure( "Tell sender requires one exact independently received lobby identity" );
    const auto expectedCharacter = identities[ 0 ];
    auto matches = [ & ]( const Json& state, const Json& row ) {
      std::vector< Json > members;
      for( const auto& member : state.at( "party" ).at( "members" ) )
        if( member.at( "entity_id" ) == expectedEntity && member.at( "name" ) == expectedName ) members.push_back( member );
      const uint64_t expectedParty = members.size() == 1 ? state.at( "party" ).at( "id" ).get< uint64_t >() : 0;
      const auto* actorRow = actor( state, expectedEntity );
      const auto& known = state.at( "known_players" );
      const auto knownIt = known.find( std::to_string( expectedEntity ) );
      const bool identityReceived =
        ( actorRow && actorRow->at( "kind" ) == 1 && actorRow->at( "name" ) == expectedName ) ||
        ( knownIt != known.end() && knownIt->at( "name" ) == expectedName ) ||
        ( members.size() == 1 && members[ 0 ].at( "character_id" ) == expectedCharacter );
      return identityReceived && row.at( "actor" ) == expectedEntity && row.at( "character_id" ) == expectedCharacter &&
             row.at( "name" ) == expectedName && row.at( "message" ) == message && row.at( "party_id" ) == expectedParty;
    };
    auto state = waitState( [ & ]( const Json& s ) {
      for( const auto& row : s.at( "tells" ) ) if( matches( s, row ) ) return true;
      return false;
    }, "exact received tell", timeout );
    const auto& tells = state.at( "tells" );
    for( auto it = tells.rbegin(); it != tells.rend(); ++it )
      if( matches( state, *it ) ) return *it;
    throw Failure( "tell vanished" );
  }

  // -- events and scenes ------------------------------------------------------

  void Bot::interact( uint32_t actorId, uint32_t eventId )
  {
    auto client = m_client;
    call( [ = ] { client->interact( actorId, eventId ); } );
  }

  Json Bot::waitScene( uint32_t eventId, uint32_t sceneId, const std::string& description, Seconds timeout )
  {
    return waitState( [ & ]( const Json& s ) {
      auto current = scene( s );
      return current && current->eventId == eventId && current->sceneId == sceneId;
    }, description, timeout );
  }

  Json Bot::waitAnyScene( Seconds timeout )
  {
    return waitState( [ & ]( const Json& s ) { return scene( s ).has_value(); }, "scene", timeout );
  }

  void Bot::chooseScene( const Json& state, const std::vector< uint32_t >& results )
  {
    auto current = scene( state );
    if( !current ) throw Failure( m_name + ": no scene to answer" );
    auto ref = current->ref();
    auto client = m_client;
    call( [ = ] { client->chooseScene( ref, results ); } );
  }

  Json Bot::answerScene( const std::vector< uint32_t >& results, Seconds timeout )
  {
    auto state = waitAnyScene( timeout );
    chooseScene( state, results );
    return state;
  }

  Json Bot::waitEventFinished( Seconds timeout )
  {
    return waitState( [ & ]( const Json& s ) { return s.at( "event_id" ).is_null() && s.at( "scene" ).is_null(); }, "event finished", timeout );
  }

  // -- gil shops --------------------------------------------------------------

  Json Bot::openGilShop( uint32_t layoutId, uint32_t eventId, Seconds timeout )
  {
    if( eventId >> 16 != 4 ) throw Failure( "unsupported gil-shop event binding" );
    interact( layoutId, eventId );
    auto state = waitScene( eventId, 0, "matching gil-shop entry scene", timeout );
    // The real client answers the entry scene with 1 (captured 2026-10-04).
    chooseScene( state, { 1 } );
    return waitScene( eventId, 40, "gil-shop item list scene", timeout );
  }

  void Bot::sellShopItem( uint32_t storage, uint32_t slot, uint32_t expectedItem )
  {
    auto state = snapshot();
    auto current = scene( state );
    if( !current ) throw Failure( "shop sale requires a received scene" );
    auto ref = current->ref();
    auto client = m_client;
    call( [ = ] { client->sellShopItem( ref, static_cast< uint16_t >( storage ), static_cast< uint16_t >( slot ), expectedItem ); } );
  }

  void Bot::buyShopItem( uint32_t eventId, uint32_t itemId, uint32_t quantity, Seconds timeout )
  {
    auto state = waitScene( eventId, 40, "refreshed gil-shop scene before purchase", timeout );
    auto ref = scene( state )->ref();
    auto client = m_client;
    call( [ = ] { client->buyShopItem( ref, eventId, itemId, quantity ); } );
  }

  Json Bot::shopBuybackRequest( uint32_t eventId, uint32_t index, uint32_t count, uint32_t price, Seconds timeout )
  {
    auto state = waitScene( eventId, 40, "gil-shop scene before buyback", timeout );
    const auto token = scene( state )->token;
    chooseScene( state, { 0, 3, index, count, price } );
    return waitState( [ & ]( const Json& s ) {
      auto current = scene( s );
      return current && current->eventId == eventId && current->sceneId == 40 && current->token != token;
    }, "shop re-listed after buyback command", timeout );
  }

  Json Bot::exitGilShop( uint32_t eventId, Seconds timeout )
  {
    auto state = waitScene( eventId, 40, "refreshed gil-shop scene", timeout );
    // The real client closes the shop with a single result of 1.
    chooseScene( state, { 1 } );
    return waitEventFinished( timeout );
  }

  // -- opening ----------------------------------------------------------------

  void Bot::startUldahOpening()
  {
    auto client = m_client;
    call( [ client ] { client->startUldahOpening(); } );
  }

  void Bot::enterUldahOpeningRange( uint32_t eventId, uint32_t param, const Point& position )
  {
    auto client = m_client;
    call( [ = ] { client->enterOpeningRange( eventId, param, position ); } );
  }

  void Bot::leaveUldahOpeningRange( uint32_t eventId, uint32_t param, const Point& position )
  {
    auto client = m_client;
    call( [ = ] { client->leaveOpeningRange( eventId, param, position ); } );
  }

  Json Bot::waitWarp( const Point& position, Seconds timeout )
  {
    return waitState( [ & ]( const Json& s ) {
      const auto& warp = s.at( "last_warp" );
      return !warp.is_null() && dist( warp.at( "position" ).get< Point >(), position ) < 0.15 &&
             dist( Bot::position( s ), position ) < 0.15;
    }, "warp to the expected position", timeout );
  }

  // -- zoning -----------------------------------------------------------------

  Json Bot::crossExit( const ExitRange& exit, uint16_t targetTerritory, Seconds timeout )
  {
    auto client = m_client;
    call( [ = ] { client->crossExit( exit, 30 ); } );
    return waitState( [ & ]( const Json& s ) {
      return s.at( "phase" ) == "ready" && s.at( "territory" ) == targetTerritory && !s.at( "between_areas" ).get< bool >();
    }, "destination territory ready", timeout );
  }

  Json Bot::discoverCentralThanalan( uint32_t layoutId, uint32_t partId, const Point& receivedPosition, uint32_t mapId, Seconds timeout )
  {
    auto client = m_client;
    call( [ = ] { client->discoverCentralThanalan( layoutId, partId, receivedPosition ); } );
    return waitState( [ & ]( const Json& s ) {
      return s.at( "discovery_reply" ) == Json{ { "map_id", mapId }, { "part_id", partId } };
    }, "source-bound discovery reply", timeout );
  }

  Json Bot::returnHomepoint( uint16_t territory, const Point& position, Seconds timeout )
  {
    auto state = snapshot();
    const auto* self = actor( state, entity( state ) );
    if( state.at( "homepoint" ) != 9 || state.at( "territory" ) != 141 || !self || self->at( "hp" ) != 0 )
      throw Failure( "homepoint return requires the supported received defeated state" );
    auto client = m_client;
    call( [ client ] { client->returnHomepoint( 30 ); } );
    return waitState( [ & ]( const Json& s ) {
      const auto* own = actor( s, entity( s ) );
      return s.at( "phase" ) == "ready" && s.at( "territory" ) == territory && dist( Bot::position( s ), position ) < 0.15 &&
             own && own->at( "hp" ).get< uint32_t >() > 0 && own->at( "hp" ) == own->at( "hp_max" );
    }, "alive at the homepoint", timeout );
  }

  Bot::ReturnCast Bot::castReturn( Seconds timeout )
  {
    const auto self = entity( snapshot() );
    auto client = m_client;
    const auto request = call( [ client ] { return client->castReturn(); } );
    auto rows = [ & ]( const Json& s, const char* table ) {
      std::vector< Json > out;
      for( const auto& row : s.at( "combat" ).at( table ) )
        if( row.at( "source" ) == self && row.at( "action" ) == 6 ) out.push_back( row );
      return out;
    };
    auto casting = waitState( [ & ]( const Json& s ) { return !rows( s, "casts" ).empty() && !rows( s, "starts" ).empty(); },
                              "received living Return cast and recast", timeout );
    const auto casts = rows( casting, "casts" ), starts = rows( casting, "starts" );
    if( casts.size() != 1 || starts.size() != 1 )
      throw Failure( "living Return did not produce one exact cast/recast pair" );
    auto state = waitState( [ & ]( const Json& s ) {
      return s.at( "phase" ) == "ready" && s.at( "territory" ) == 130 && !s.at( "between_areas" ).get< bool >();
    }, "living Return destination ready", timeout );
    return { state, request, casts[ 0 ], starts[ 0 ] };
  }

  // -- party ------------------------------------------------------------------

  Json Bot::inviteParty( uint32_t target, const std::string& name, Seconds timeout )
  {
    auto client = m_client;
    call( [ = ] { client->inviteParty( target, name ); } );
    return waitState( [ & ]( const Json& s ) {
      const auto& result = s.at( "party_invite_result" );
      return !result.is_null() && result.at( "target" ) == name;
    }, "matching party invite result", timeout );
  }

  Json Bot::acceptParty( unsigned expectedCount, Seconds timeout )
  {
    if( expectedCount < 2 || expectedCount > 8 ) throw Failure( "party acceptance requires a bounded expected roster size" );
    waitState( [ & ]( const Json& s ) { return !s.at( "pending_party_invite" ).is_null(); }, "received pending party invite", timeout );
    auto client = m_client;
    call( [ client ] { client->acceptParty(); } );
    return waitState( [ & ]( const Json& s ) { return s.at( "party" ).at( "count" ) == expectedCount; },
                      "received " + std::to_string( expectedCount ) + "-member party state", timeout );
  }

  Json Bot::declineParty( Seconds timeout )
  {
    auto pending = waitState( [ & ]( const Json& s ) { return !s.at( "pending_party_invite" ).is_null(); },
                              "received pending party invite", timeout ).at( "pending_party_invite" );
    auto client = m_client;
    call( [ client ] { client->declineParty(); } );
    const Json expected{ { "result", 0 }, { "auth_type", 1 }, { "answer", 0 }, { "name", pending.at( "name" ) } };
    auto state = waitState( [ & ]( const Json& s ) {
      return s.at( "party_invite_reply" ) == expected && s.at( "party" ).at( "count" ) == 0;
    }, "exact received party decline result", timeout );
    return state.at( "party_invite_reply" );
  }

  Json Bot::leaveParty( Seconds timeout )
  {
    auto client = m_client;
    call( [ client ] { client->leaveParty(); } );
    return waitState( [ & ]( const Json& s ) { return s.at( "party" ).at( "count" ) == 0; }, "received empty party state", timeout );
  }

  Json Bot::disbandParty( Seconds timeout )
  {
    auto client = m_client;
    call( [ client ] { client->disbandParty(); } );
    return waitState( [ & ]( const Json& s ) { return s.at( "party" ).at( "count" ) == 0; }, "received empty disbanded party state", timeout );
  }

  Json Bot::kickPartyMember( uint32_t target, const std::string& name, Seconds timeout )
  {
    auto client = m_client;
    call( [ = ] { client->kickPartyMember( target, name ); } );
    return waitState( [ & ]( const Json& s ) {
      if( s.at( "party" ).at( "count" ) < 2 ) return false;
      for( const auto& member : s.at( "party" ).at( "members" ) )
        if( member.at( "entity_id" ) == target ) return false;
      return true;
    }, "exact received party roster after kick", timeout );
  }

  Json Bot::changePartyLeader( uint32_t target, const std::string& name, Seconds timeout )
  {
    auto client = m_client;
    call( [ = ] { client->changePartyLeader( target, name ); } );
    return waitState( [ & ]( const Json& s ) {
      const auto& party = s.at( "party" );
      if( party.at( "count" ) < 2 ) return false;
      const auto& leader = party.at( "members" )[ party.at( "leader_index" ).get< size_t >() ];
      return leader.at( "entity_id" ) == target && leader.at( "name" ) == name;
    }, "exact received party leader change", timeout );
  }

  Testing::PartyChannel Bot::partyChat( const std::string& message )
  {
    auto client = m_client;
    return call( [ = ] { return client->partyChat( message ); } );
  }

  Json Bot::expectPartyChat( const Json& senderState, const std::string& message, Seconds timeout )
  {
    const auto sender = entity( senderState );
    auto matches = [ & ]( const Json& state, const Json& row ) {
      std::vector< Json > members;
      for( const auto& member : state.at( "party" ).at( "members" ) )
        if( member.at( "entity_id" ) == sender ) members.push_back( member );
      return members.size() == 1 && row.at( "actor" ) == sender && row.at( "character_id" ) == members[ 0 ].at( "character_id" ) &&
             row.at( "name" ) == members[ 0 ].at( "name" ) && row.at( "message" ) == message &&
             row.at( "party_id" ) == state.at( "party" ).at( "id" ) && row.at( "channel" ) == state.at( "party" ).at( "chat_channel" );
    };
    auto state = waitState( [ & ]( const Json& s ) {
      for( const auto& row : s.at( "party_chat" ) ) if( matches( s, row ) ) return true;
      return false;
    }, "exact received party chat", timeout );
    const auto& rows = state.at( "party_chat" );
    for( auto it = rows.rbegin(); it != rows.rend(); ++it )
      if( matches( state, *it ) ) return *it;
    throw Failure( "party chat vanished" );
  }

  // -- combat -----------------------------------------------------------------

  Json Bot::expectActionEffect( uint32_t action, uint32_t target, uint32_t request, const std::string& description, Seconds timeout )
  {
    auto find = [ & ]( const Json& s ) -> const Json* {
      for( const auto& e : s.at( "combat" ).at( "effects" ) )
        if( e.at( "source" ) == s.at( "entity_id" ) && e.at( "target" ) == target && e.at( "action" ) == action && e.at( "request" ) == request )
          return &e;
      return nullptr;
    };
    auto state = waitState( [ & ]( const Json& s ) { return find( s ) != nullptr; }, description, timeout );
    return *find( state );
  }

  Bot::ActionResult Bot::sprint( Seconds timeout )
  {
    auto client = m_client;
    const auto request = call( [ client ] { return client->sprint(); } );
    auto state = waitState( [ & ]( const Json& s ) {
      for( const auto& e : s.at( "combat" ).at( "effects" ) )
        if( e.at( "source" ) == s.at( "entity_id" ) && e.at( "target" ) == s.at( "entity_id" ) && e.at( "action" ) == 3 && e.at( "request" ) == request )
          return true;
      return false;
    }, "exact Sprint action effect", timeout );
    return { state, request };
  }

  Json Bot::waitSprintReady( Seconds timeout )
  {
    return waitState( sprintReady, "received Sprint-ready state", timeout );
  }

  Json Bot::waitActionReady( StarterAction action, uint32_t target, Seconds timeout )
  {
    return waitState( [ & ]( const Json& s ) { return actionReady( s, action, target ); },
                      "action " + std::to_string( static_cast< uint32_t >( action ) ) + " ready: local guard, resources and estimated range", timeout );
  }

  Json Bot::action( StarterAction action, uint32_t target, Seconds timeout )
  {
    auto client = m_client;
    const auto request = call( [ = ] { return client->starterAction( action, target ); } );
    return expectActionEffect( static_cast< uint32_t >( action ), target, request,
                               "matching effect for action " + std::to_string( static_cast< uint32_t >( action ) ), timeout );
  }

  Bot::ItemUse Bot::useShopVfxItem( uint32_t storage, uint32_t slot, uint32_t expectedCount, Seconds timeout )
  {
    auto before = snapshot();
    const auto self = entity( before );
    auto count = [ & ]( const Json& s ) {
      size_t n = 0;
      for( const auto& row : s.at( "combat" ).at( "effects" ) )
        if( row.at( "source" ) == self && row.at( "target" ) == self && row.at( "action" ) == 5890 ) ++n;
      return n;
    };
    const auto old = count( before );
    auto client = m_client;
    const auto request = call( [ = ] { return client->useShopVfxItem( storage, slot, expectedCount ); } );
    auto state = waitState( [ & ]( const Json& s ) { return count( s ) > old; }, "exact source-bound shop VFX item effect", timeout );
    Json effect;
    for( const auto& row : state.at( "combat" ).at( "effects" ) )
      if( row.at( "source" ) == self && row.at( "target" ) == self && row.at( "action" ) == 5890 ) effect = row;
    return { state, effect, request };
  }

  // -- inventory --------------------------------------------------------------

  uint32_t Bot::waitOperationAcknowledged( uint32_t context, uint32_t operation, const std::string& description, Seconds timeout )
  {
    waitState( [ & ]( const Json& s ) {
      for( const auto& row : s.at( "rewards" ).at( "operation_batches" ) )
        if( row.at( "context" ) == context && row.at( "operation" ) == operation && row.at( "error" ) == 0 ) return true;
      return false;
    }, description + " acknowledgement (not inventory mutation)", timeout );
    return context;
  }

  void Bot::discardItem( uint32_t storage, uint32_t slot, uint32_t expectedItem, Seconds timeout )
  {
    auto client = m_client;
    call( [ = ] { client->discardItem( storage, slot, expectedItem ); } );
    const auto key = slotKey( storage, slot );
    waitState( [ & ]( const Json& s ) { return s.at( "rewards" ).at( "inventory_ready" ).get< bool >() && !inventory( s ).contains( key ); },
               "discarded stack removed from the received inventory", timeout );
  }

  uint32_t Bot::requestItemUnequip( uint32_t gearSlot, uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedItem, Seconds timeout )
  {
    auto client = m_client;
    const auto context = call( [ = ] { return client->unequipItem( gearSlot, expectedItem, destinationStorage, destinationSlot ); } );
    return waitOperationAcknowledged( context, 8, "unequip", timeout );
  }

  uint32_t Bot::requestShopItemEquip( uint32_t storage, uint32_t slot, uint32_t expectedItem, uint32_t gearSlot, Seconds timeout )
  {
    auto client = m_client;
    const auto context = call( [ = ] { return client->equipShopItem( storage, slot, expectedItem, gearSlot ); } );
    return waitOperationAcknowledged( context, 8, "equip", timeout );
  }

  uint32_t Bot::requestItemReequipStarter( uint32_t storage, uint32_t slot, uint32_t expectedItem, uint32_t gearSlot, Seconds timeout )
  {
    auto client = m_client;
    const auto context = call( [ = ] { return client->reequipStarterItem( storage, slot, expectedItem, gearSlot ); } );
    return waitOperationAcknowledged( context, 8, "re-equip", timeout );
  }

  uint32_t Bot::requestCurrencyMoveRejection( uint32_t expectedGil, Seconds timeout )
  {
    auto client = m_client;
    const auto context = call( [ = ] { return client->currencyMoveRejection( expectedGil ); } );
    // The server answers the rejected move with the batch only; the gil row is unchanged.
    waitState( [ & ]( const Json& s ) {
      for( const auto& row : s.at( "rewards" ).at( "operation_batches" ) )
        if( row.at( "context" ) == context ) return true;
      return false;
    }, "currency move acknowledgement", timeout );
    return context;
  }

  uint32_t Bot::requestItemMove( uint32_t storage, uint32_t slot, uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedItem, Seconds timeout )
  {
    auto client = m_client;
    const auto context = call( [ = ] { return client->moveItem( storage, slot, expectedItem, destinationStorage, destinationSlot ); } );
    return waitOperationAcknowledged( context, 8, "move", timeout );
  }

  uint32_t Bot::requestItemSwap( uint32_t storage, uint32_t slot, uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedItem, uint32_t expectedDestinationItem, Seconds timeout )
  {
    auto client = m_client;
    const auto context = call( [ = ] { return client->swapItem( storage, slot, expectedItem, destinationStorage, destinationSlot, expectedDestinationItem ); } );
    return waitOperationAcknowledged( context, 9, "swap", timeout );
  }

  uint32_t Bot::requestItemSplit( uint32_t storage, uint32_t slot, uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedItem, uint32_t expectedCount, uint32_t splitCount, Seconds timeout )
  {
    auto client = m_client;
    const auto context = call( [ = ] { return client->splitItem( storage, slot, expectedItem, expectedCount, splitCount, destinationStorage, destinationSlot ); } );
    return waitOperationAcknowledged( context, 10, "split", timeout );
  }

  uint32_t Bot::requestItemMerge( uint32_t storage, uint32_t slot, uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedItem, uint32_t expectedCount, uint32_t expectedDestinationCount, Seconds timeout )
  {
    auto client = m_client;
    const auto context = call( [ = ] { return client->mergeItem( storage, slot, expectedItem, expectedCount, destinationStorage, destinationSlot, expectedDestinationCount ); } );
    return waitOperationAcknowledged( context, 12, "merge", timeout );
  }

  // -- rewards and quests -----------------------------------------------------

  Bot::Rewards Bot::rewardValues( const Json& state, size_t workIndex )
  {
    const auto& rewards = state.at( "rewards" );
    if( !rewards.at( "inventory_ready" ).get< bool >() || rewards.at( "exp_by_index" ).size() <= workIndex )
      throw Failure( "reward baseline is not observed yet" );
    Rewards result;
    for( const auto& slot : rewards.at( "inventory" ) )
    {
      const auto storage = slot.at( "storage" ).get< uint32_t >();
      if( storage > 3 && storage != 2000 ) continue;
      auto& target = storage == 2000 ? result.currencies : result.items;
      target[ slot.at( "id" ).get< uint32_t >() ] += slot.at( "count" ).get< uint32_t >();
    }
    const auto job = std::to_string( rewards.at( "class_job" ).get< uint32_t >() );
    const auto& byClass = rewards.at( "exp_by_class" );
    result.exp = byClass.contains( job ) ? byClass.at( job ).get< uint32_t >() : rewards.at( "exp_by_index" )[ workIndex ].get< uint32_t >();
    result.level = rewards.at( "level" ).is_null() ? rewards.at( "level_by_index" )[ workIndex ].get< uint32_t >() : rewards.at( "level" ).get< uint32_t >();
    return result;
  }

  Bot::Rewards Bot::rewardSnapshot( size_t workIndex, Seconds timeout )
  {
    auto state = waitState( [ & ]( const Json& s ) {
      return s.at( "rewards" ).at( "inventory_ready" ).get< bool >() && s.at( "rewards" ).at( "exp_by_index" ).size() > workIndex;
    }, "inventory and experience snapshot", timeout );
    return rewardValues( state, workIndex );
  }

  Json Bot::expectRewards( const Rewards& expected, size_t workIndex, Seconds timeout )
  {
    return waitState( [ & ]( const Json& s ) {
      return s.at( "rewards" ).at( "inventory_ready" ).get< bool >() && s.at( "rewards" ).at( "exp_by_index" ).size() > workIndex &&
             rewardValues( s, workIndex ) == expected;
    }, "exact reward state", timeout );
  }

  Json Bot::expectQuestActive( uint32_t quest, std::optional< uint32_t > sequence, Seconds timeout )
  {
    const auto key = std::to_string( quest & 0xffff );
    return waitState( [ & ]( const Json& s ) {
      const auto& quests = s.at( "quests" );
      return quests.contains( key ) && ( !sequence || quests.at( key ).at( "sequence" ) == *sequence );
    }, "quest " + std::to_string( quest ) + " active", timeout );
  }

  Json Bot::expectQuestComplete( uint32_t quest, Seconds timeout )
  {
    const auto key = std::to_string( quest & 0xffff );
    return waitState( [ & ]( const Json& s ) {
      const auto& complete = s.at( "complete_quests" );
      return complete.contains( key ) && complete.at( key ) == true;
    }, "quest " + std::to_string( quest ) + " complete", timeout );
  }

  // -- readiness checks -------------------------------------------------------

  static bool guardClear( const Json& state )
  {
    return state.at( "combat" ).at( "starting_action_guard_remaining_ms" ).get< uint32_t >() == 0;
  }

  static bool idle( const Json& state )
  {
    return state.at( "phase" ) == "ready" && !state.at( "moving" ).get< bool >() && state.at( "event_id" ).is_null() && state.at( "scene" ).is_null();
  }

  bool sprintReady( const Json& state )
  {
    if( !idle( state ) ) return false;
    if( state.at( "gm_rank" ) != 0 ) throw Failure( "Sprint readiness requires a non-GM player" );
    const auto* own = Bot::actor( state, Bot::entity( state ) );
    if( !own ) return false;
    if( own->at( "kind" ) != 1 || own->at( "hp" ).get< int >() <= 0 ) throw Failure( "player was defeated while waiting for Sprint readiness" );
    return guardClear( state ) && own->at( "tp" ).get< int >() >= 50;
  }

  bool actionReady( const Json& state, StarterAction action, uint32_t target )
  {
    if( !idle( state ) ) return false;
    uint32_t classJob = 1, minimumLevel = 1; int cost = 60; double range = 2.5; bool usesMp = false; const char* name = "Gladiator";
    switch( action )
    {
      case StarterAction::FastBlade: break;
      case StarterAction::SavageBlade: minimumLevel = 4; break;
      case StarterAction::Bootshine: classJob = 2; name = "Pugilist"; break;
      case StarterAction::TrueStrike: classJob = 2; name = "Pugilist"; minimumLevel = 2; cost = 50; break;
      case StarterAction::Blizzard: classJob = 7; name = "Thaumaturge"; usesMp = true; cost = 4; range = 24.5; break;
    }
    if( state.at( "gm_rank" ) != 0 || state.at( "rewards" ).at( "class_job" ) != classJob )
      throw Failure( std::string( "readiness requires a non-GM " ) + name );
    const auto* own = Bot::actor( state, Bot::entity( state ) );
    const auto* enemy = Bot::actor( state, target );
    if( !own || !enemy ) return false;
    if( own->at( "hp" ).get< int >() <= 0 ) throw Failure( "fighter was defeated while waiting for combat readiness" );
    if( enemy->at( "kind" ) != 2 || enemy->at( "hp" ).get< int >() <= 0 ) return false;
    if( own->at( "level" ).get< uint32_t >() < minimumLevel ) throw Failure( std::string( name ) + " actor level does not satisfy the source action" );
    const auto resource = own->at( usesMp ? "mp" : "tp" ).get< int >();
    if( !guardClear( state ) || resource < cost || dist( Bot::predicted( state ), enemy->at( "position" ).get< Point >() ) > range )
      return false;
    if( action == StarterAction::SavageBlade )
    {
      // The latest own effect must be a Fast Blade on this target carrying the combo marker.
      const auto& effects = state.at( "combat" ).at( "effects" );
      for( auto it = effects.rbegin(); it != effects.rend(); ++it )
      {
        if( it->at( "source" ) != state.at( "entity_id" ) ) continue;
        if( it->at( "target" ) != target || it->at( "action" ) != 9 ) return false;
        for( const auto& effect : it->value( "source_effects", Json::array() ) )
          if( effect == Json{ { "type", 29 }, { "value", 9 }, { "flag", 0x80 }, { "args", { 0, 0, 0 } } } ) return true;
        return false;
      }
      return false;
    }
    return true;
  }

  uint32_t damageValue( const Json& effect )
  {
    uint32_t total = 0;
    for( const auto& row : effect.at( "effects" ) )
      if( ( row.at( "type" ) == 3 || row.at( "type" ) == 5 ) && row.at( "flag" ) == 0 )
        total += row.at( "value" ).get< uint32_t >();
    return total;
  }

  bool committedDamage( const Json& state, const Json& effect, const Json& before )
  {
    const auto damage = damageValue( effect );
    if( damage == 0 ) return false;
    bool present = false;
    for( const auto& row : state.at( "combat" ).at( "effects" ) ) if( row == effect ) present = true;
    if( !present ) return false;
    const auto hpBefore = before.at( "hp" ).get< int64_t >();
    for( const auto& row : state.at( "combat" ).at( "integrities" ) )
      if( row.at( "target" ) == effect.at( "target" ) && row.at( "result" ) == effect.at( "result" ) &&
          row.at( "hp_max" ) == before.at( "hp_max" ) && row.at( "hp" ).get< int64_t >() == std::max< int64_t >( 0, hpBefore - damage ) )
        return true;
    return false;
  }
}
