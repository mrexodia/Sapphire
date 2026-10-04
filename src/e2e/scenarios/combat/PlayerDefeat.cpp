// A natural level-14 enemy versus a level-one player: the player opens with one
// Fast Blade, runs beyond the 40m leash so the enemy retreats to spawn and
// heals, re-engages, is pursued along a short route and defeated, returns to
// the Ul'dah homepoint alive and at full health, and a fresh login shows the
// same place with EXP, level, currency and inventory unchanged. No grants,
// relocation or injected damage.
#include "../../harness/Combat.h"
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"
#include <chrono>
#include <set>

using namespace Sapphire::E2E;

class PlayerDefeat : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto home = homepoint( data, Homepoints::Uldah );
    expect( home.territory == Uldah::Territory, "homepoint 9 returns to Ul'dah" );
    const auto spawn = population( ctx, CentralThanalan::Territory ).spawn( CentralThanalan::LevelFourteenSpawn );
    expect( spawn.baseId == CentralThanalan::LevelFourteenEnemy && spawn.level == 14 && !spawn.nonpop,
            "the level-14 spawn is an ordinary population of the expected kind" );
    data.navi( CentralThanalan::Territory );
    // Both routes are authored around this enemy's spawn, so the scenario keeps
    // the exact spawn: a short pursuit leg and a leash leg past the 40m retreat.
    const auto start = beside( spawn.position );
    const auto pursuit = boundedRoute( data, CentralThanalan::Territory, start, spawn.position, 10, 8, 20 );
    const auto leash = boundedRoute( data, CentralThanalan::Territory, start, spawn.position, 50, 45, 70 );
    expect( distance( pursuit.points.front(), spawn.position ) <= 3 && distance( leash.points.front(), spawn.position ) <= 3,
            "both routes start beside the enemy" );
    ctx.log( "pursuit route " + std::to_string( pursuit.length ).substr( 0, 5 ) + "m, leash route " + std::to_string( leash.length ).substr( 0, 5 ) + "m" );

    CharacterOptions fighterOptions;
    fighterOptions.territory = CentralThanalan::Territory;
    fighterOptions.position = start;
    CharacterOptions observerOptions = fighterOptions;
    observerOptions.position = spawn.position;
    ( *observerOptions.position )[ 0 ] -= 30.0f;
    CharacterOptions returnOptions;
    returnOptions.territory = home.territory;
    returnOptions.position = home.popRange.position;
    auto& observer = ctx.spawnCharacter( "defeat-observer", observerOptions );
    auto& returnObserver = ctx.spawnCharacter( "return-observer", returnOptions );
    auto& fighter = ctx.spawnCharacter( "defeated-fighter", fighterOptions );
    const auto fixture = ctx.fixture( fighter );
    const auto initial = waitRewardsObserved( fighter, 1 );
    const auto entity = Bot::entity( initial );
    const Json before = *Bot::actor( initial, entity );
    const auto beforeRewards = Bot::rewardValues( initial, 1 );
    const auto beforeInventory = initial.at( "rewards" ).at( "inventory" );
    expect( before.at( "hp" ) == before.at( "hp_max" ) && before.at( "hp" ).get< int >() > 0 && before.at( "level" ) == 1,
            "the fighter is a full-health level-one player" );
    observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, entity ) != nullptr; }, "fighter visible", 20 );

    // With navigation active the enemy roams and may have been killed by another
    // scenario, so allow one respawn and a wider search; the opening approach
    // below follows it using received positions.
    auto boundEnemy = [ & ]( const Json& s, const Json& actor ) {
      return actor.at( "kind" ) == 2 && actor.at( "base_id" ) == spawn.baseId && actor.at( "level" ) == spawn.level &&
             actor.at( "layout_id" ) == spawn.layoutId && actor.at( "hp" ).get< int64_t >() > 0 && actor.at( "hp" ) == actor.at( "hp_max" ) &&
             distance( actor.at( "position" ).get< Point >(), Bot::position( s ) ) < 40;
    };
    auto state = fighter.waitState( [ & ]( const Json& s ) {
      for( const auto& [ key, actor ] : s.at( "actors" ).items() )
        if( boundEnemy( s, actor ) ) return true;
      return false;
    }, "source-layout level-14 enemy healthy within 40m (allow one respawn)", 150 );
    uint32_t target = 0;
    for( const auto& [ key, actor ] : state.at( "actors" ).items() )
      if( boundEnemy( state, actor ) ) { target = static_cast< uint32_t >( std::stoul( key ) ); break; }
    observer.waitState( [ & ]( const Json& s ) {
      const auto* enemy = Bot::actor( s, target );
      return enemy && enemy->at( "layout_id" ) == spawn.layoutId && enemy->at( "hp" ).get< int64_t >() > 0 && enemy->at( "hp" ) == enemy->at( "hp_max" );
    }, "observer independently receives bounded opening target", 20 );
    fighter.waitState( [ & ]( const Json& s ) {
      const auto* own = Bot::actor( s, entity );
      return own && own->at( "tp" ).get< int >() >= 60;
    }, "naturally regenerated opening TP", 10 );

    // The enemy may roam while TP regenerates. Follow bounded received positions
    // with normal movement, every reached point witnessed.
    std::vector< Point > openingApproach;
    bool reached = false;
    for( int leg = 0; leg < 8 && !reached; ++leg )
    {
      state = fighter.snapshot();
      const auto* enemy = Bot::actor( state, target );
      expect( enemy && enemy->at( "hp" ).get< int64_t >() > 0 && enemy->at( "hp" ) == enemy->at( "hp_max" ), "the opening target is still healthy" );
      const auto enemyPosition = enemy->at( "position" ).get< Point >();
      const auto gap = distance( enemyPosition, Bot::predicted( state ) );
      if( gap < 2.5 )
      {
        reached = true;
        break;
      }
      expect( gap < 45, "natural opening target left bounded follow range" );
      const auto destination = beside( enemyPosition );
      fighter.walkTo( destination, 2.0f, 15 );
      observer.waitState( [ & ]( const Json& s ) {
        const auto* own = Bot::actor( s, entity );
        return own && distance( own->at( "position" ).get< Point >(), destination ) < 0.15;
      }, "observer sees bounded opening approach", 15 );
      openingApproach.push_back( destination );
    }
    expect( reached, "bounded opening approach did not reach the natural target" );
    state = fighter.waitActionReady( StarterAction::FastBlade, target );
    const auto enemyStart = Bot::actor( state, target )->at( "position" ).get< Point >();
    const auto openingEffect = fighter.action( StarterAction::FastBlade, target );
    expect( openingEffect.at( "target" ) == target && damageValue( openingEffect ) > 0, "the opening Fast Blade hits the target" );
    ctx.log( "opened after " + std::to_string( openingApproach.size() ) + " witnessed legs; " + std::to_string( damageValue( openingEffect ) ) + " damage" );

    // Drive beyond the 40m spawn-distance retreat threshold.
    auto enemyPositionOr = [ & ]( const Json& s, const Point& fallback ) {
      const auto* enemy = Bot::actor( s, target );
      return enemy ? enemy->at( "position" ).get< Point >() : fallback;
    };
    Json leashPeak;
    double leashPeakDistance = 0;
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds( 30 );
    for( const auto& point : leash.points )
    {
      const auto remaining = std::chrono::duration< double >( deadline - std::chrono::steady_clock::now() ).count();
      expect( remaining > 0, "leash route exceeded its deadline" );
      const auto current = fighter.walkTo( point, 6.0f, remaining );
      const auto fromSpawn = distance( enemyPositionOr( current, enemyStart ), spawn.position );
      if( fromSpawn > leashPeakDistance )
      {
        leashPeak = current;
        leashPeakDistance = fromSpawn;
      }
    }
    // Position replication is coarser than the FSM tick; a received >35m pursuit
    // followed by the return to spawn proves the retreat transition.
    if( leashPeakDistance <= 35 )
    {
      leashPeak = fighter.waitState( [ & ]( const Json& s ) {
        const auto* own = Bot::actor( s, entity );
        return own && own->at( "hp" ).get< int64_t >() > 0 && distance( enemyPositionOr( s, enemyStart ), spawn.position ) > 35;
      }, "enemy approaches source-defined leash threshold", 30 );
      leashPeakDistance = distance( Bot::actor( leashPeak, target )->at( "position" ).get< Point >(), spawn.position );
    }
    observer.waitState( [ & ]( const Json& s ) {
      const auto* own = Bot::actor( s, entity );
      return own && distance( own->at( "position" ).get< Point >(), leash.points.back() ) < 0.15;
    }, "observer sees fighter complete leash route", 30 );
    const auto reset = fighter.waitState( [ & ]( const Json& s ) {
      const auto* own = Bot::actor( s, entity );
      const auto* enemy = Bot::actor( s, target );
      return own && own->at( "hp" ).get< int64_t >() > 0 && enemy && distance( enemy->at( "position" ).get< Point >(), spawn.position ) < 2;
    }, "enemy retreats to spawn while fighter survives", 45 );
    const auto healthReset = fighter.waitState( [ & ]( const Json& s ) {
      const auto* enemy = Bot::actor( s, target );
      return enemy && enemy->at( "hp" ).get< int64_t >() > 0 && enemy->at( "hp" ) == enemy->at( "hp_max" );
    }, "retreated enemy health reset", 10 );
    const Json resetEnemy = *Bot::actor( healthReset, target );
    const auto observerHealthReset = observer.waitState( [ & ]( const Json& s ) {
      const auto* enemy = Bot::actor( s, target );
      return enemy && enemy->at( "hp" ) == resetEnemy.at( "hp" );
    }, "observer sees retreated enemy health reset", 10 );
    expect( Bot::actor( observerHealthReset, target )->at( "hp_max" ) == resetEnemy.at( "hp_max" ), "both clients agree on the reset enemy's max HP" );
    ctx.log( "leash peak " + std::to_string( leashPeakDistance ).substr( 0, 5 ) + "m from spawn; enemy back at spawn with " +
             Bot::actor( reset, target )->at( "hp" ).dump() + " HP, healed to " + resetEnemy.at( "hp" ).dump() );

    std::vector< Point > back( leash.points.rbegin(), leash.points.rend() );
    fighter.walkRoute( back, 6.0f, 30 );
    observer.waitState( [ & ]( const Json& s ) {
      const auto* own = Bot::actor( s, entity );
      return own && distance( own->at( "position" ).get< Point >(), leash.points.front() ) < 0.15;
    }, "observer sees fighter return to reset enemy", 30 );
    fighter.waitState( [ & ]( const Json& s ) {
      const auto* enemy = Bot::actor( s, target );
      return enemy && distance( enemy->at( "position" ).get< Point >(), Bot::predicted( s ) ) < 3;
    }, "returned fighter reaches reset enemy", 30 );
    fighter.waitActionReady( StarterAction::FastBlade, target );
    const auto secondOpening = fighter.action( StarterAction::FastBlade, target );
    expect( secondOpening.at( "target" ) == target && damageValue( secondOpening ) > 0, "the second opening Fast Blade hits the target" );
    const auto pursuitEnemyStart = Bot::actor( fighter.snapshot(), target )->at( "position" ).get< Point >();

    fighter.walkRoute( pursuit.points, 6.0f, 30 );
    observer.waitState( [ & ]( const Json& s ) {
      const auto* own = Bot::actor( s, entity );
      return own && distance( own->at( "position" ).get< Point >(), pursuit.points.back() ) < 0.15;
    }, "independent observer sees fighter complete pursuit route", 30 );
    auto moved = [ & ]( const Json& s ) { return distance( enemyPositionOr( s, pursuitEnemyStart ), pursuitEnemyStart ) >= 2; };
    const auto pursued = fighter.waitState( moved, "hostile natural enemy pursuit", 30 );
    const auto pursuedObserver = observer.waitState( moved, "observer sees hostile natural enemy pursuit", 30 );
    // The two snapshots are independent and the enemy is still moving, and a
    // chasing enemy may pass the fighter's endpoint between snapshots, so require
    // independently received movement of at least 2m projected toward that endpoint.
    Point routeVector{};
    for( size_t axis = 0; axis < 3; ++axis )
      routeVector[ axis ] = pursuit.points.back()[ axis ] - pursuit.points.front()[ axis ];
    const auto routeLength = std::sqrt( routeVector[ 0 ] * routeVector[ 0 ] + routeVector[ 1 ] * routeVector[ 1 ] + routeVector[ 2 ] * routeVector[ 2 ] );
    expect( routeLength > 5, "the pursuit route displaces the fighter" );
    for( const auto* observed : { &pursued, &pursuedObserver } )
    {
      const auto position = Bot::actor( *observed, target )->at( "position" ).get< Point >();
      double displacementLength = 0, projection = 0;
      for( size_t axis = 0; axis < 3; ++axis )
      {
        const double d = position[ axis ] - pursuitEnemyStart[ axis ];
        displacementLength += d * d;
        projection += d * routeVector[ axis ];
      }
      displacementLength = std::sqrt( displacementLength );
      projection /= routeLength;
      expect( displacementLength >= 2 && projection >= 2 && projection / displacementLength > 0.5,
              "the enemy moved at least 2m toward the fighter's endpoint" );
    }

    const auto defeated = fighter.waitState( [ & ]( const Json& s ) {
      const auto* own = Bot::actor( s, entity );
      return own && own->at( "hp" ) == 0;
    }, "natural hostile-enemy player defeat", 90 );
    std::vector< Json > incoming;
    size_t starts = 0;
    for( const auto& row : defeated.at( "combat" ).at( "effects" ) )
      if( row.at( "target" ) == entity && row.at( "kind" ) == 1 && damageValue( row ) > 0 ) incoming.push_back( row );
    for( const auto& row : defeated.at( "combat" ).at( "starts" ) )
      if( row.at( "source" ) == entity && row.at( "action" ) == 9 ) ++starts;
    expect( !incoming.empty() && starts == 2, "the fighter was hit and started exactly two Fast Blades" );
    std::set< uint32_t > sources;
    for( const auto& row : incoming )
      sources.insert( row.at( "source" ).get< uint32_t >() );
    expect( sources.size() == 1, "one enemy did all the damage" );
    const auto source = *sources.begin();
    const Json enemy = *Bot::actor( defeated, source );
    expect( enemy.at( "base_id" ) == spawn.baseId && enemy.at( "level" ) == 14 && enemy.at( "hp" ).get< int64_t >() > 0 &&
            enemy.at( "hp" ).get< int64_t >() < enemy.at( "hp_max" ).get< int64_t >(), "the damaged level-14 enemy survives" );
    expect( distance( enemy.at( "position" ).get< Point >(), pursuit.points.back() ) < 4, "the enemy stands at the fighter's endpoint" );
    requireUnchangedDeathState( beforeRewards, beforeInventory, Bot::rewardValues( defeated, 1 ), defeated.at( "rewards" ).at( "inventory" ) );

    const auto observed = observer.waitState( [ & ]( const Json& s ) {
      const auto* own = Bot::actor( s, entity );
      return own && own->at( "hp" ) == 0;
    }, "observer sees player defeat", 20 );
    std::vector< Json > observerIncoming;
    for( const auto& row : observed.at( "combat" ).at( "effects" ) )
      if( row.at( "source" ) == source && row.at( "target" ) == entity && row.at( "kind" ) == 1 && damageValue( row ) > 0 ) observerIncoming.push_back( row );
    expect( observerIncoming == incoming, "the observer received the identical incoming effects" );
    for( const auto* view : { &defeated, &observed } )
    {
      std::map< std::pair< uint32_t, uint32_t >, Json > integrities;
      for( const auto& row : view->at( "combat" ).at( "integrities" ) )
        integrities[ { row.at( "target" ).get< uint32_t >(), row.at( "result" ).get< uint32_t >() } ] = row;
      for( const auto& effect : incoming )
      {
        const auto committed = integrities.at( { entity, effect.at( "result" ).get< uint32_t >() } );
        const auto previous = committed.at( "previous_hp" ).get< int64_t >();
        expect( committed.at( "hp" ).get< int64_t >() == std::max< int64_t >( 0, previous - damageValue( effect ) ), "each hit committed exactly its damage" );
        expect( committed.at( "hp" ).get< int64_t >() < previous && previous <= before.at( "hp_max" ).get< int64_t >(), "each hit lowered HP from at most max HP" );
        expect( committed.at( "hp_max" ) == before.at( "hp_max" ), "max HP is unchanged through the defeat" );
      }
      expect( integrities.at( { entity, incoming.back().at( "result" ).get< uint32_t >() } ).at( "hp" ) == 0, "the last hit committed zero HP" );
    }
    size_t incomingIntegrities = 0;
    std::set< uint32_t > results;
    for( const auto& row : incoming )
      results.insert( row.at( "result" ).get< uint32_t >() );
    for( const auto& row : defeated.at( "combat" ).at( "integrities" ) )
      if( row.at( "target" ) == entity && results.count( row.at( "result" ).get< uint32_t >() ) ) ++incomingIntegrities;
    expect( incomingIntegrities == incoming.size(), "one integrity per incoming hit" );
    ctx.log( "defeated by " + std::to_string( incoming.size() ) + " hits; enemy left with " + enemy.at( "hp" ).dump() + " HP" );

    const auto returned = fighter.returnHomepoint( home.territory, home.popRange.position );
    observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, entity ) == nullptr; }, "defeated fighter leaves Central Thanalan", 30 );
    const auto returnSeen = returnObserver.waitState( [ & ]( const Json& s ) {
      const auto* own = Bot::actor( s, entity );
      return own && own->at( "hp" ) == own->at( "hp_max" ) && distance( own->at( "position" ).get< Point >(), home.popRange.position ) < 0.15;
    }, "independent observer sees living fighter at homepoint", 30 );
    expect( returned.at( "homepoint" ) == 9 && returned.at( "territory" ) == Uldah::Territory, "the fighter returned to homepoint 9 in Ul'dah" );
    const Json returnedSelf = *Bot::actor( returned, entity );
    expect( returnedSelf.at( "hp" ) == returnedSelf.at( "hp_max" ) && returnedSelf.at( "hp_max" ) == before.at( "hp_max" ), "the fighter returned at full health" );
    expect( Bot::actor( returnSeen, entity )->at( "hp" ) == returnedSelf.at( "hp" ), "the return observer sees the same health" );
    requireUnchangedDeathState( beforeRewards, beforeInventory, Bot::rewardValues( returned, 1 ), returned.at( "rewards" ).at( "inventory" ) );

    fighter.logout();
    returnObserver.waitState( [ & ]( const Json& s ) { return Bot::actor( s, entity ) == nullptr; }, "returned fighter session cleanup", 30 );
    observer.logout();
    returnObserver.logout();
    auto& reloaded = ctx.spawn( "returned-reloaded" );
    reloaded.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
    const auto persisted = waitRewardsObserved( reloaded, 1 );
    const Json persistedSelf = *Bot::actor( persisted, Bot::entity( persisted ) );
    expect( persisted.at( "territory" ) == home.territory, "the fighter restarted in the homepoint territory" );
    expect( distance( Bot::position( persisted ), home.popRange.position ) < 0.15, "the fighter restarted at the homepoint" );
    expect( persistedSelf.at( "hp" ) == persistedSelf.at( "hp_max" ) && persistedSelf.at( "hp_max" ) == before.at( "hp_max" ), "the fighter restarted at full health" );
    requireUnchangedDeathState( beforeRewards, beforeInventory, Bot::rewardValues( persisted, 1 ), persisted.at( "rewards" ).at( "inventory" ) );
    reloaded.logout();
  }
};

EXPOSE_SCENARIO( PlayerDefeat );
