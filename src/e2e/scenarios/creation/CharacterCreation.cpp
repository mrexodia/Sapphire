// Normal lobby character creation for every Ul'dah opening ring branch and
// starting class; the opening's first scenes; the closed arrival area and a
// closed city exit (Wymond's line, then the warp back to the layout's return
// spots); the arrival area falling silent once Coming to Ul'dah is accepted;
// starter gear and ring equip/unequip round trips proven across fresh logins;
// one duplicate-name rejection and one normal deletion. Inventory operation
// acknowledgements are never taken as mutation proof: every change is read
// back after a fresh login. Needs SkipOpening = false on the world.
#include "../../harness/Context.h"
#include "../../harness/Opening.h"
#include "../../harness/Scenario.h"
#include <cmath>
#include <optional>

using namespace Sapphire::E2E;
using namespace Sapphire::E2E::UldahOpening;

namespace
{
  // Scene answers the real client sends in the opening (capture profile sapphire-3.3).
  constexpr uint32_t Finish = 0;                 // 1245187 scenes 1, 20, 30 and 40
  constexpr uint32_t AcceptComingToUldah = 1;    // 66130 scene 0
  constexpr uint32_t ContinueComingToUldah = 0;  // 66130 scenes 1 and 2
  constexpr uint32_t Ring1 = 11, Ring2 = 12;     // gear set slots
  constexpr uint32_t GearStorage = 1000;

  struct Branch
  {
    const char* choice;
    uint32_t ringResult;     // the answer to scene 0 that picks the ring
    uint32_t item;
    uint8_t classJob;
    std::vector< uint32_t > gearSlots;  // starter gear unequipped before the opening
  };
  const std::vector< Branch > branches{
    { "choose_ring_4423", 1, 4423, 1, { 0, 3, 4, 6, 7 } },
    { "choose_ring_4424", 2, 4424, 2, { 0 } },
    { "choose_ring_4425", 3, 4425, 7, { 0 } },
    { "choose_ring_4426", 4, 4426, 1, {} } };

  struct Move
  {
    uint32_t item = 0, gearSlot = 0;
    std::string from, to;    // "<storage>:<slot>" keys
  };

  struct Record
  {
    Account account;
    uint32_t item = 0;
    size_t workIndex = 0;
    Bot::Rewards expected;
    Json inventory;          // after re-equipping the gear and the ring
    std::string ringSlot;    // the bag slot the ring was granted to
    std::optional< Point > openingPosition;
    bool questActive = false;
  };

  std::pair< uint32_t, uint32_t > splitKey( const std::string& key )
  {
    return { static_cast< uint32_t >( std::stoul( key.substr( 0, key.find( ':' ) ) ) ),
             static_cast< uint32_t >( std::stoul( key.substr( key.find( ':' ) + 1 ) ) ) };
  }

  Json moved( Json row, uint32_t storage, uint32_t slot )
  {
    row[ "storage" ] = storage;
    row[ "slot" ] = slot;
    return row;
  }

  // Move a row of the expected inventory between two keys.
  void relocate( Json& inventory, const std::string& from, const std::string& to )
  {
    const auto [ storage, slot ] = splitKey( to );
    auto row = inventory.at( from );
    inventory.erase( from );
    inventory[ to ] = moved( row, storage, slot );
  }

  double dist( const Point& a, const Point& b )
  {
    return std::hypot( a[ 0 ] - b[ 0 ], a[ 1 ] - b[ 1 ], a[ 2 ] - b[ 2 ] );
  }

  Json openingScene( const Json& state )
  {
    const auto scene = Bot::scene( state );
    return scene && scene->eventId == EventId ? state.at( "scene" ) : Json();
  }
}

class CharacterCreation : public Scenario
{
  // Wait for Wymond's line and dismiss it.
  static void finishRangeScene( Bot& bot, const std::string& description )
  {
    bot.chooseScene( bot.waitScene( EventId, RangeScene, description ), { Finish } );
    bot.waitEventFinished();
  }

  // The opening continuation after a fresh login must be the given scene.
  static Json continueOpening( Bot& bot, uint32_t sceneId, const std::string& description, uint64_t previousToken = 0 )
  {
    auto state = bot.waitState( [ & ]( const Json& s ) {
      const auto scene = openingScene( s );
      return !scene.is_null() && scene.at( "token" ) != previousToken;
    }, description );
    const auto scene = Bot::scene( state );
    expect( scene->sceneId == sceneId, description + ": expected scene " + std::to_string( sceneId ) + ", got " + std::to_string( scene->sceneId ) );
    bot.chooseScene( state, { Finish } );
    return state;
  }

  void run( Context& ctx ) override
  {
    const auto opening = uldahOpening( ctx.data() );
    ctx.log( "closed exit " + std::to_string( opening.closedExit.range.id ) + " reached over " + std::to_string( opening.rangeRouteLength ).substr( 0, 5 ) +
             " m; Wymond over " + std::to_string( opening.approachRouteLength ).substr( 0, 5 ) + " m" );
    std::vector< Record > records;

    for( size_t index = 0; index < branches.size(); ++index )
    {
      const auto& branch = branches[ index ];
      const auto suffix = std::to_string( index );
      const auto account = ctx.server().freshAccount();
      auto& player = ctx.spawn( "new-character-" + suffix );
      auto state = player.createCharacterViaLobby( account.auth, account.name, branch.classJob );
      expect( state.at( "created_via_lobby" ) == true && state.at( "territory" ) == Territory, "a new character starts in the opening instance" );
      if( index == 0 )
      {
        const auto duplicateAccount = ctx.server().freshAccount();
        auto& duplicate = ctx.spawn( "new-character-duplicate-name" );
        const auto rejected = duplicate.expectNameRejected( duplicateAccount.auth, account.name );
        expect( rejected.at( "characters" ).empty(), "a rejected name creates no character" );
        duplicate.close();
        ctx.log( "duplicate name rejected: " + rejected.at( "name_rejection" ).dump() );
      }
      const auto entity = Bot::entity( state );
      expect( state.at( "gm_rank" ) == 0 && Bot::actor( state, entity )->at( "level" ) == 1, "a new character is a non-GM level one" );
      expect( state.at( "rewards" ).at( "class_job" ) == branch.classJob, "the chosen starting class is active" );
      expect( state.at( "characters" ).size() == 1 && state.at( "characters" )[ 0 ].at( "name" ) == account.name, "the lobby lists exactly the new character" );
      size_t workIndex = 0;
      unsigned levelOnes = 0;
      const auto& levels = state.at( "rewards" ).at( "level_by_index" );
      for( size_t i = 0; i < levels.size(); ++i )
        if( levels[ i ] == 1 )
        {
          workIndex = i;
          ++levelOnes;
        }
      expect( levelOnes == 1, "exactly one class is level one" );
      const auto before = player.rewardSnapshot( workIndex );
      expect( before.items.empty() && before.exp == 0 && before.level == 1, "a new character owns nothing beyond its gear" );
      Json expectedInventory = Bot::inventory( player.snapshot() );
      std::vector< Move > unequipped;
      for( const auto gearSlot : branch.gearSlots )
      {
        const auto gearKey = Bot::slotKey( GearStorage, gearSlot );
        const auto source = expectedInventory.at( gearKey );
        const auto destination = Bot::emptyBagSlot( expectedInventory );
        expect( source.at( "count" ) == 1, "starter gear is a single piece" );
        const auto [ storage, slot ] = splitKey( destination );
        player.requestItemUnequip( gearSlot, storage, slot, source.at( "id" ).get< uint32_t >() );
        relocate( expectedInventory, gearKey, destination );
        unequipped.push_back( { source.at( "id" ).get< uint32_t >(), gearSlot, gearKey, destination } );
      }

      player.startUldahOpening();
      const auto first = player.waitAnyScene( 10 );
      const auto firstScene = *Bot::scene( first );
      if( firstScene.eventId != EventId || firstScene.sceneId != 0 )
        throw Failure( "the opening did not start at its first scene; this scenario needs SkipOpening = false in the world's config" );
      player.chooseScene( first, { branch.ringResult } );
      const auto chained = player.waitScene( EventId, 1, "source-defined chained Ul'dah opening scene 1" );
      expect( chained.at( "territory" ) == Territory && chained.at( "gm_rank" ) == 0, "the opening keeps the character in its instance" );
      player.chooseScene( chained, { Finish } );
      player.waitEventFinished();

      // Opening sequence 1: leaving the arrival area is answered by Wymond's
      // line and a warp back to the layout's return spot.
      player.leaveUldahOpeningRange( EventId, ArrivalArea, Bot::predicted( player.snapshot() ) );
      finishRangeScene( player, "arrival-area scene during opening sequence 1" );
      player.waitWarp( opening.arrivalArea.returnPosition );

      // A closed city exit: the same line, then a warp back to that exit's return spot.
      player.walkRoute( opening.rangeRoute, 2.0f, 15 );
      player.enterUldahOpeningRange( EventId, ClosedExit, opening.rangeRoute.back() );
      finishRangeScene( player, "source-defined opening within-range scene" );
      player.waitWarp( opening.closedExit.returnPosition );
      auto expected = before;
      expected.items[ branch.item ] = 1;
      for( const auto& move : unequipped )
        expected.items[ move.item ] = 1;
      // The opening grant is deliberately silent on this server. Locate and
      // bind the ring only from the authoritative fresh-login inventory below.
      const auto ringSlot = Bot::emptyBagSlot( expectedInventory );
      {
        const auto [ storage, slot ] = splitKey( ringSlot );
        expectedInventory[ ringSlot ] = Json{ { "storage", storage }, { "slot", slot }, { "id", branch.item }, { "count", 1 } };
      }
      player.logout( 10, true );

      auto& reloaded = ctx.spawn( "new-character-reloaded-" + suffix );
      state = reloaded.loginViaLobby( ctx.server().relogin( account ), account.name );
      expect( state.at( "created_via_lobby" ) == false && state.at( "territory" ) == Territory && state.at( "gm_rank" ) == 0,
              "the created character logs back into the opening instance" );
      // The warp-back position is what persisted, not the spot where the range was entered.
      expect( dist( Bot::position( state ), opening.closedExit.returnPosition ) < 0.15, "the warp-back position persisted" );
      state = reloaded.expectRewards( expected, workIndex );
      Json inventory = Bot::inventory( state );
      expect( inventory == expectedInventory, "the fresh-login inventory shows the unequipped gear and the ring; got " + inventory.dump() );
      for( const auto& move : unequipped )
      {
        const auto [ storage, slot ] = splitKey( move.to );
        reloaded.requestItemReequipStarter( storage, slot, move.item, move.gearSlot );
        relocate( inventory, move.to, Bot::slotKey( GearStorage, move.gearSlot ) );
        expected.items.erase( move.item );
      }
      const auto [ ringStorage, ringIndex ] = splitKey( ringSlot );
      reloaded.requestItemReequipStarter( ringStorage, ringIndex, branch.item, Ring1 );
      relocate( inventory, ringSlot, Bot::slotKey( GearStorage, Ring1 ) );
      expected.items.erase( branch.item );
      unsigned rings = 0;
      for( const auto& row : inventory )
        if( row.at( "id" ) == branch.item && row.at( "count" ) == 1 )
          ++rings;
      expect( rings == 1, "exactly one ring of the chosen kind" );

      // OpeningSequence=1 must select scene 40 after fresh authentication, not replay scene 0.
      reloaded.startUldahOpening();
      continueOpening( reloaded, 40, "persisted Ul'dah opening continuation" );
      reloaded.waitEventFinished();
      std::optional< Point > openingPosition;
      bool questActive = false;
      if( index == 0 )
      {
        reloaded.walkRoute( opening.approachRoute, 2.0f, 30 );
        reloaded.interact( opening.giver.id, ComingToUldah );
        reloaded.chooseScene( reloaded.waitScene( ComingToUldah, 0, "Coming to Ul'dah offer" ), { AcceptComingToUldah } );
        reloaded.chooseScene( reloaded.waitScene( ComingToUldah, 1, "Coming to Ul'dah scene 1" ), { ContinueComingToUldah } );
        reloaded.chooseScene( reloaded.waitScene( ComingToUldah, 2, "Coming to Ul'dah scene 2" ), { ContinueComingToUldah } );
        reloaded.waitEventFinished();
        reloaded.expectQuestActive( ComingToUldah, 255 );
        openingPosition = opening.approachRoute.back();
        questActive = true;
        // Opening sequence 2 (quest accepted): the client still reports the
        // arrival area, but leaving it must now be silent, otherwise the line
        // repeats on the way to Momodi.
        const auto mark = reloaded.now();
        reloaded.leaveUldahOpeningRange( EventId, ArrivalArea, Bot::predicted( reloaded.snapshot() ) );
        reloaded.waitState( [ & ]( const Json& ) {
          for( const auto& entry : reloaded.journal( mark ) )
            if( entry.event == "event_finish" )
              return true;
          return false;
        }, "arrival-area event finished" );
        for( const auto& entry : reloaded.journal( mark ) )
          expect( entry.event != "scene" && entry.event != "warp", "leaving the arrival area after accepting the quest must be silent, got " + entry.event );
        ctx.log( "Coming to Ul'dah accepted; the arrival area is silent" );
      }
      reloaded.logout( 10, true );
      records.push_back( { account, branch.item, workIndex, expected, inventory, ringSlot, openingPosition, questActive } );
      ctx.log( std::string( "branch " ) + branch.choice + " (class " + std::to_string( branch.classJob ) + ") created and verified" );
    }

    for( size_t index = 0; index < records.size(); ++index )
    {
      const auto& record = records[ index ];
      const auto& account = record.account;
      const auto suffix = std::to_string( index );
      auto& restarted = ctx.spawn( "new-character-restarted-" + suffix );
      auto state = restarted.loginViaLobby( ctx.server().relogin( account ), account.name );
      expect( state.at( "territory" ) == Territory && state.at( "gm_rank" ) == 0, "the character is still in the opening instance" );
      state = restarted.expectRewards( record.expected, record.workIndex );
      expect( Bot::inventory( state ) == record.inventory, "the re-equipped gear and ring persisted; got " + Bot::inventory( state ).dump() );
      if( record.questActive )
      {
        restarted.expectQuestActive( ComingToUldah, 255 );
        expect( dist( Bot::position( state ), *record.openingPosition ) < 0.15, "the position beside Wymond persisted" );
      }
      restarted.startUldahOpening();
      auto scene = continueOpening( restarted, 40, "restarted Ul'dah opening continuation" );
      if( record.questActive )
        continueOpening( restarted, 30, "OpeningSequence=2 chained scene", Bot::scene( scene )->token );
      restarted.waitEventFinished();
      const auto [ ringStorage, ringIndex ] = splitKey( record.ringSlot );
      restarted.requestItemUnequip( Ring1, ringStorage, ringIndex, record.item );
      Json finalInventory = record.inventory;
      relocate( finalInventory, Bot::slotKey( GearStorage, Ring1 ), record.ringSlot );
      auto finalExpected = record.expected;
      finalExpected.items[ record.item ] = 1;
      restarted.logout( 10, true );

      auto& roundtrip = ctx.spawn( "new-character-ring-roundtrip-" + suffix );
      state = roundtrip.loginViaLobby( ctx.server().relogin( account ), account.name );
      expect( state.at( "territory" ) == Territory && state.at( "gm_rank" ) == 0, "the character is still in the opening instance" );
      state = roundtrip.expectRewards( finalExpected, record.workIndex );
      expect( Bot::inventory( state ) == finalInventory, "the unequipped ring persisted in its bag slot; got " + Bot::inventory( state ).dump() );
      roundtrip.requestItemReequipStarter( ringStorage, ringIndex, record.item, Ring2 );
      Json ring2Inventory = finalInventory;
      relocate( ring2Inventory, record.ringSlot, Bot::slotKey( GearStorage, Ring2 ) );
      auto ring2Expected = finalExpected;
      ring2Expected.items.erase( record.item );
      roundtrip.logout( 10, true );

      auto& ring2Restarted = ctx.spawn( "new-character-ring2-restarted-" + suffix );
      state = ring2Restarted.loginViaLobby( ctx.server().relogin( account ), account.name );
      state = ring2Restarted.expectRewards( ring2Expected, record.workIndex );
      expect( Bot::inventory( state ) == ring2Inventory, "the ring persisted in the second ring slot; got " + Bot::inventory( state ).dump() );
      ring2Restarted.requestItemUnequip( Ring2, ringStorage, ringIndex, record.item );
      ring2Restarted.logout( 10, true );

      auto& ring2Final = ctx.spawn( "new-character-ring2-final-" + suffix );
      state = ring2Final.loginViaLobby( ctx.server().relogin( account ), account.name );
      state = ring2Final.expectRewards( finalExpected, record.workIndex );
      expect( Bot::inventory( state ) == finalInventory, "the ring persisted back in its bag slot; got " + Bot::inventory( state ).dump() );
      ring2Final.logout();
      ctx.log( "ring round trips of " + account.name + " persisted" );

      if( index == 0 )
      {
        auto& deleter = ctx.spawn( "new-character-delete" );
        const auto deleted = deleter.deleteCharacterViaLobby( ctx.server().relogin( account ), account.name );
        expect( deleted.at( "characters" ).empty() && deleted.at( "created_via_lobby" ) == false, "the refreshed lobby list no longer has the character" );
        deleter.close();
        auto& absent = ctx.spawn( "new-character-delete-verify" );
        const auto verified = absent.expectCharacterAbsent( ctx.server().relogin( account ), account.name );
        expect( verified.at( "characters" ).empty() && verified.at( "deleted_via_lobby" ) == false, "a fresh HTTP and lobby session confirms the deletion" );
        absent.close();
        ctx.log( account.name + " deleted and confirmed absent" );
      }
    }
  }
};

EXPOSE_SCENARIO( CharacterCreation );
