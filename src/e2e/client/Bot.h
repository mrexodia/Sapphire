#pragma once
// A bot as a scenario sees it: synchronous calls on the scenario thread that
// send a request and wait for the received state to show the outcome. Sending
// is never success; the state the server sent back is.
#include "Client.h"
#include <condition_variable>
#include <deque>
#include <functional>
#include <future>
#include <mutex>
#include <string>

namespace Sapphire::E2E
{
  using Testing::Json;
  using Testing::Point;
  using Testing::SceneRef;
  using Testing::ExitRange;
  using Testing::StarterAction;
  using Testing::LoginOptions;

  struct Auth;

  struct Timeout : std::runtime_error { using std::runtime_error::runtime_error; };

  struct JournalEntry
  {
    std::chrono::steady_clock::time_point at;
    std::string event;
    Json data;
  };

  struct Scene
  {
    uint32_t eventId = 0;
    uint32_t sceneId = 0;
    uint64_t token = 0;
    SceneRef ref() const { return { eventId, sceneId, token }; }
  };

  class Bot
  {
  public:
    using Predicate = std::function< bool( const Json& ) >;
    using Seconds = double;

    Bot( asio::io_service& io, std::string name );
    ~Bot();
    Bot( const Bot& ) = delete;
    Bot& operator=( const Bot& ) = delete;

    const std::string& name() const { return m_name; }

    // -- state --------------------------------------------------------------
    Json snapshot();
    // Wait until the predicate holds for a snapshot; throws Timeout with the
    // description and a state excerpt otherwise. Bot failures throw too.
    Json waitState( const Predicate& predicate, const std::string& description, Seconds timeout = 30 );
    std::vector< JournalEntry > journal( std::chrono::steady_clock::time_point since = {} );
    std::chrono::steady_clock::time_point now() const { return std::chrono::steady_clock::now(); }

    // Convenience readers over a snapshot.
    static uint32_t entity( const Json& s ) { return s.at( "entity_id" ).get< uint32_t >(); }
    static Point position( const Json& s ) { return s.at( "observed_position" ).get< Point >(); }
    static Point predicted( const Json& s ) { return s.at( "predicted_position" ).get< Point >(); }
    static const Json* actor( const Json& s, uint32_t id );
    static std::optional< Scene > scene( const Json& s );
    static uint32_t gil( const Json& s );
    static const Json& inventory( const Json& s ) { return s.at( "rewards" ).at( "inventory" ); }
    static std::string slotKey( uint32_t storage, uint32_t slot ) { return std::to_string( storage ) + ":" + std::to_string( slot ); }
    // First empty ordinary bag slot ("<bag>:<slot>") given an inventory map.
    static std::string emptyBagSlot( const Json& inventory );

    // -- lobby --------------------------------------------------------------
    Json loginViaLobby( const Auth& auth, const std::string& character, Seconds timeout = 30 );
    Json createCharacterViaLobby( const Auth& auth, const std::string& character, uint8_t creationClass = 1, Seconds timeout = 30 );
    Json deleteCharacterViaLobby( const Auth& auth, const std::string& character, Seconds timeout = 30 );
    Json expectNameRejected( const Auth& auth, const std::string& character, Seconds timeout = 30 );
    Json expectCharacterAbsent( const Auth& auth, const std::string& character, Seconds timeout = 30 );
    Json waitWorldReady( Seconds timeout = 30 );
    void logout( Seconds timeout = 10, bool waitServerClose = false );
    void close();

    // -- movement and chat --------------------------------------------------
    Json walkTo( const Point& position, float speed = 2.0f, Seconds timeout = 60 );
    void walkRoute( const std::vector< Point >& waypoints, float speed = 2.0f, Seconds timeout = 300 );
    void say( const std::string& message );
    Json expectSay( uint32_t actor, const std::string& message, Seconds timeout = 10 );
    void tell( uint32_t target, const std::string& name, const std::string& message );
    void tellRemote( uint32_t target, const std::string& name, const std::string& message );
    void tellVisible( uint32_t target, const std::string& name, const std::string& message );
    Json tellOffline( uint32_t target, const std::string& name, const std::string& message, Seconds timeout = 10 );
    Json expectTell( const Json& senderState, const std::string& message, Seconds timeout = 10 );

    // -- events and scenes --------------------------------------------------
    void interact( uint32_t actorId, uint32_t eventId );
    Json waitScene( uint32_t eventId, uint32_t sceneId, const std::string& description, Seconds timeout = 10 );
    Json waitAnyScene( Seconds timeout = 10 );
    void chooseScene( const Json& state, const std::vector< uint32_t >& results );
    // Answer whatever scene is up next with the given results.
    Json answerScene( const std::vector< uint32_t >& results, Seconds timeout = 10 );
    Json waitEventFinished( Seconds timeout = 10 );

    // -- gil shops ----------------------------------------------------------
    Json openGilShop( uint32_t layoutId, uint32_t eventId, Seconds timeout = 10 );
    void sellShopItem( uint32_t storage, uint32_t slot, uint32_t expectedItem );
    void buyShopItem( uint32_t eventId, uint32_t itemId, uint32_t quantity, Seconds timeout = 10 );
    Json shopBuybackRequest( uint32_t eventId, uint32_t index, uint32_t count, uint32_t price, Seconds timeout = 10 );
    Json exitGilShop( uint32_t eventId, Seconds timeout = 10 );

    // -- opening ------------------------------------------------------------
    void startUldahOpening();
    void enterUldahOpeningRange( uint32_t eventId, uint32_t param, const Point& position );
    void leaveUldahOpeningRange( uint32_t eventId, uint32_t param, const Point& position );
    Json waitWarp( const Point& position, Seconds timeout = 10 );

    // -- zoning -------------------------------------------------------------
    Json crossExit( const ExitRange& exit, uint16_t targetTerritory, Seconds timeout = 60 );
    Json discoverCentralThanalan( uint32_t layoutId, uint32_t partId, const Point& receivedPosition, uint32_t mapId, Seconds timeout = 10 );
    Json returnHomepoint( uint16_t territory, const Point& position, Seconds timeout = 30 );
    struct ReturnCast { Json state; uint32_t request; Json cast; Json start; };
    ReturnCast castReturn( Seconds timeout = 30 );

    // -- party --------------------------------------------------------------
    Json inviteParty( uint32_t target, const std::string& name, Seconds timeout = 10 );
    Json acceptParty( unsigned expectedCount = 2, Seconds timeout = 10 );
    Json declineParty( Seconds timeout = 10 );
    Json leaveParty( Seconds timeout = 10 );
    Json disbandParty( Seconds timeout = 10 );
    Json kickPartyMember( uint32_t target, const std::string& name, Seconds timeout = 10 );
    Json changePartyLeader( uint32_t target, const std::string& name, Seconds timeout = 10 );
    Testing::PartyChannel partyChat( const std::string& message );
    Json expectPartyChat( const Json& senderState, const std::string& message, Seconds timeout = 10 );

    // -- combat -------------------------------------------------------------
    struct ActionResult { Json state; uint32_t request; };
    ActionResult sprint( Seconds timeout = 10 );
    Json waitSprintReady( Seconds timeout = 30 );
    // Wait until the local pacing guard, resources and estimated range allow the action.
    Json waitActionReady( StarterAction action, uint32_t target, Seconds timeout = 30 );
    // Send the action and wait for its effect on the target; returns the effect row.
    Json action( StarterAction action, uint32_t target, Seconds timeout = 10 );
    struct ItemUse { Json state; Json effect; uint32_t request; };
    ItemUse useShopVfxItem( uint32_t storage, uint32_t slot, uint32_t expectedCount = 3, Seconds timeout = 10 );

    // -- inventory (acknowledgement is not mutation proof) ------------------
    void discardItem( uint32_t storage, uint32_t slot, uint32_t expectedItem, Seconds timeout = 10 );
    uint32_t requestItemUnequip( uint32_t gearSlot, uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedItem, Seconds timeout = 10 );
    uint32_t requestShopItemEquip( uint32_t storage, uint32_t slot, uint32_t expectedItem, uint32_t gearSlot, Seconds timeout = 10 );
    uint32_t requestItemReequipStarter( uint32_t storage, uint32_t slot, uint32_t expectedItem, uint32_t gearSlot, Seconds timeout = 10 );
    uint32_t requestCurrencyMoveRejection( uint32_t expectedGil, Seconds timeout = 10 );
    uint32_t requestItemMove( uint32_t storage, uint32_t slot, uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedItem, Seconds timeout = 10 );
    uint32_t requestItemSwap( uint32_t storage, uint32_t slot, uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedItem, uint32_t expectedDestinationItem, Seconds timeout = 10 );
    uint32_t requestItemSplit( uint32_t storage, uint32_t slot, uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedItem, uint32_t expectedCount, uint32_t splitCount, Seconds timeout = 10 );
    uint32_t requestItemMerge( uint32_t storage, uint32_t slot, uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedItem, uint32_t expectedCount, uint32_t expectedDestinationCount, Seconds timeout = 10 );

    // -- rewards and quests -------------------------------------------------
    struct Rewards
    {
      std::map< uint32_t, uint32_t > items;      // item id -> count in ordinary bags
      std::map< uint32_t, uint32_t > currencies; // currency item id -> count
      uint32_t exp = 0;
      uint32_t level = 0;
      bool operator==( const Rewards& other ) const
      { return items == other.items && currencies == other.currencies && exp == other.exp && level == other.level; }
      bool operator!=( const Rewards& other ) const { return !( *this == other ); }
    };
    static Rewards rewardValues( const Json& state, size_t workIndex );
    Rewards rewardSnapshot( size_t workIndex, Seconds timeout = 10 );
    Json expectRewards( const Rewards& expected, size_t workIndex, Seconds timeout = 10 );
    Json expectQuestActive( uint32_t quest, std::optional< uint32_t > sequence = std::nullopt, Seconds timeout = 10 );
    Json expectQuestComplete( uint32_t quest, Seconds timeout = 10 );

  private:
    template< class F > auto call( F&& function ) -> decltype( function() );
    void onEvent( const Json& event );
    Json waitLobbyPhase( const LoginOptions& options, const std::string& phase, const std::string& description, Seconds timeout );
    Json expectActionEffect( uint32_t action, uint32_t target, uint32_t request, const std::string& description, Seconds timeout );
    uint32_t waitOperationAcknowledged( uint32_t context, uint32_t operation, const std::string& description, Seconds timeout );

    asio::io_service& m_io;
    std::string m_name;
    std::shared_ptr< Testing::Client > m_client;
    std::mutex m_mutex;
    std::condition_variable m_changed;
    uint64_t m_version = 0;
    std::deque< JournalEntry > m_journal;
    std::string m_failure;
  };

  // Combat readiness checks over received state (mirrors the real client's
  // own gating: pacing guard, resources, estimated range).
  bool sprintReady( const Json& state );
  bool actionReady( const Json& state, StarterAction action, uint32_t target );
  uint32_t damageValue( const Json& effect );
  bool committedDamage( const Json& state, const Json& effect, const Json& targetBefore );
}
