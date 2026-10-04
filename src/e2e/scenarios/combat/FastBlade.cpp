// A level-one Gladiator defeats a natural level-one marmot with paced Fast
// Blades while a witness sees every hit: committed damage at both clients, the
// marmot's retaliation against the still-full-health fighter, the fixed EXP and
// delayed testTable loot, and the same rewards after a fresh login. No spawned
// enemies, granted resources or skills.
#include "../../harness/Combat.h"
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"
#include <chrono>
#include <set>

using namespace Sapphire::E2E;

class FastBlade : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto fastBlade = actionMeta( data, 9 );
    expect( fastBlade == Json{ { "action", 9 }, { "class_job", 1 }, { "work_index", 1 }, { "level", 1 }, { "base_exp", 50 },
                               { "category", 3 }, { "cost_type", 5 }, { "cost", 60 }, { "range", -1 }, { "cast_ms", 0 },
                               { "recast_ms", 2500 }, { "recast_group", 58 }, { "effect_type", 1 }, { "target_enemy", true } },
            "Fast Blade metadata matches the supported level-one profile: " + fastBlade.dump() );
    const size_t workIndex = fastBlade.at( "work_index" ).get< size_t >();
    const uint32_t baseExp = fastBlade.at( "base_exp" ).get< uint32_t >();

    // The unchanged world population, not a hand-authored enemy spawn.
    const auto spawn = population( ctx, CentralThanalan::Territory ).spawn( CentralThanalan::FastBladeMarmotSpawn );
    expect( spawn.baseId == CentralThanalan::Marmot && spawn.level == 1 && !spawn.nonpop, "the marmot spawn is an ordinary level-one population" );
    data.navi( CentralThanalan::Territory );   // enemies cannot move without a navmesh

    CharacterOptions options;
    options.territory = CentralThanalan::Territory;
    options.position = beside( spawn.position );
    auto& fighter = ctx.spawnCharacter( "fighter", options );
    const auto fixture = ctx.fixture( fighter );
    auto state = fighter.snapshot();
    const auto entity = Bot::entity( state );
    expect( Bot::actor( state, entity )->at( "level" ) == fastBlade.at( "level" ), "the fixture is level one" );
    expect( state.at( "rewards" ).at( "class_job" ) == fastBlade.at( "class_job" ), "the fixture is a Gladiator" );
    const auto beforeRewards = fighter.rewardSnapshot( workIndex );
    auto& observer = ctx.spawnCharacter( "combat-observer", options );
    observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, entity ) != nullptr; }, "fighter visible" );

    // Wandering is genuine server behaviour: the marmot roams up to 6m from
    // its spawn, so walk up to it, then wait for it in range with natural TP.
    const auto nearby = waitHealthyEnemy( fighter, CentralThanalan::Marmot, 1, 60.0, 90 );
    approachTarget( fighter, nearby.first, 2.0, 6, 2.0f );
    auto candidates = [ & ]( const Json& s ) { return healthyEnemies( s, CentralThanalan::Marmot, 1, 2.0 ); };
    state = fighter.waitState( [ & ]( const Json& s ) {
      return !candidates( s ).empty() && Bot::actor( s, entity )->at( "tp" ).get< int >() >= 60;
    }, "nearby level-one marmot and naturally regenerated TP (respawn takes 15s)", 60 );
    const auto target = candidates( state ).front().first;
    const auto fighterBefore = *Bot::actor( state, entity );
    expect( fighterBefore.at( "hp" ) == fighterBefore.at( "hp_max" ) && fighterBefore.at( "hp" ).get< int >() > 0, "the fighter starts at full health" );

    int64_t expectedHp = candidates( state ).front().second.at( "hp" ).get< int64_t >();
    std::vector< Json > effects;
    std::vector< std::chrono::steady_clock::time_point > attempts;
    std::set< uint32_t > requests, results;
    std::map< std::string, Json > committedStates;
    while( expectedHp > 0 )
    {
      expect( effects.size() < 16, "bounded Fast Blade sequence did not defeat the level-one target" );
      // The marmot may step away between hits; close the gap with received positions.
      approachTarget( fighter, target );
      // No fixed sleep around the action: await natural TP and the client's local
      // pacing guard, which the received ActionStart extends.
      state = fighter.waitActionReady( StarterAction::FastBlade, target );
      const auto before = *Bot::actor( state, target );
      expect( before.at( "hp" ).get< int64_t >() == expectedHp && expectedHp > 0, "the fighter sees the exact committed target HP" );
      observer.waitState( [ & ]( const Json& s ) {
        const auto* enemy = Bot::actor( s, target );
        const auto* own = Bot::actor( s, entity );
        return enemy && own && enemy->at( "hp" ) == before.at( "hp" ) && own->at( "hp" ).get< int >() > 0 &&
               distance( enemy->at( "position" ).get< Point >(), own->at( "position" ).get< Point >() ) < 3;
      }, "observer sees target HP and living fighter within melee range" );
      attempts.push_back( std::chrono::steady_clock::now() );
      if( attempts.size() > 1 )
        expect( std::chrono::duration< double >( attempts.back() - attempts[ attempts.size() - 2 ] ).count() >= 2.5,
                "Fast Blades are paced at least 2.5s apart" );
      const auto effect = fighter.action( StarterAction::FastBlade, target );
      expect( effect.at( "kind" ) == 1 && damageValue( effect ) > 0, "Fast Blade is a damaging kind-1 effect" );
      expect( requests.insert( effect.at( "request" ).get< uint32_t >() ).second, "every Fast Blade carries a new request id" );
      expect( results.insert( effect.at( "result" ).get< uint32_t >() ).second, "every Fast Blade carries a new result id" );
      effects.push_back( effect );
      for( Bot* bot : { &fighter, &observer } )
      {
        const auto observed = bot->waitState( [ & ]( const Json& s ) { return committedDamage( s, effect, before ); },
                                              "identical effect and matching committed HP decrease", 10 );
        expect( observed.at( "phase" ) == "ready" && observed.at( "gm_rank" ) == 0 && observed.at( "territory" ) == CentralThanalan::Territory,
                bot->name() + " is a ready non-GM client in Central Thanalan" );
        expect( observed.at( "scene" ).is_null(), bot->name() + " has no scene open" );
        committedStates[ bot->name() ] = observed;
      }
      const auto started = fighter.waitState( [ & ]( const Json& s ) {
        size_t count = 0;
        for( const auto& row : s.at( "combat" ).at( "starts" ) )
          if( row.at( "source" ) == entity && row.at( "action" ) == 9 ) ++count;
        return count == effects.size();
      }, "one received Fast Blade start per request", 10 );
      for( const auto& row : started.at( "combat" ).at( "starts" ) )
        if( row.at( "source" ) == entity && row.at( "action" ) == 9 )
          expect( row.at( "group" ) == 58 && row.at( "recast_centiseconds" ) == 250, "Fast Blade starts carry group 58 and a 2.5s recast" );
      expectedHp = std::max< int64_t >( 0, before.at( "hp" ).get< int64_t >() - damageValue( effect ) );
      ctx.log( "Fast Blade " + std::to_string( effects.size() ) + ": " + std::to_string( damageValue( effect ) ) + " damage, target HP " +
               std::to_string( before.at( "hp" ).get< int64_t >() ) + " -> " + std::to_string( expectedHp ) );
    }
    expect( effects.size() >= 3, "a level-one marmot takes at least three Fast Blades" );
    for( const auto& [ name, observed ] : committedStates )
      expect( Bot::actor( observed, target )->at( "hp" ) == 0, name + " saw the target at zero HP" );

    // The marmot fought back: the first positive hit against the previously
    // full-health fighter. Later ticks regenerate HP; never infer a pre-hit value.
    auto incoming = [ & ]( const Json& s ) {
      std::vector< Json > rows;
      for( const auto& row : s.at( "combat" ).at( "effects" ) )
        if( row.at( "source" ) == target && row.at( "target" ) == entity && row.at( "action" ) == 7 && damageValue( row ) > 0 )
          rows.push_back( row );
      return rows;
    };
    state = fighter.waitState( [ & ]( const Json& s ) { return !incoming( s ).empty(); }, "natural marmot retaliation", 15 );
    const auto retaliation = incoming( state ).front();
    expect( retaliation.at( "kind" ) == 1 && retaliation.at( "request" ) == 0, "the retaliation is an unrequested kind-1 auto-attack" );
    for( Bot* bot : { &fighter, &observer } )
    {
      const auto observed = bot->waitState( [ & ]( const Json& s ) { return committedDamage( s, retaliation, fighterBefore ); },
                                            "independently observed first retaliation effect and exact committed HP", 10 );
      expect( Bot::actor( observed, entity )->at( "hp" ).get< int >() > 0, "the fighter survives the retaliation" );
      expect( observed.at( "phase" ) == "ready" && observed.at( "territory" ) == CentralThanalan::Territory && observed.at( "gm_rank" ) == 0,
              bot->name() + " stays a ready non-GM client" );
      expect( observed.at( "scene" ).is_null() && observed.at( "event_id" ).is_null(), bot->name() + " has no event open" );
    }

    // Fixed EXP and the delayed testTable loot.
    auto count = []( const Bot::Rewards& rewards, uint32_t item ) -> int64_t {
      auto it = rewards.items.find( item );
      return it == rewards.items.end() ? 0 : it->second;
    };
    auto receivedKillRewards = [ & ]( const Json& s ) {
      if( !s.at( "rewards" ).at( "inventory_ready" ).get< bool >() || s.at( "rewards" ).at( "exp_by_index" ).size() <= workIndex )
        return false;
      const auto current = Bot::rewardValues( s, workIndex );
      const bool firstPool = ( count( current, 8 ) - count( beforeRewards, 8 ) == 5 ) != ( count( current, 9 ) - count( beforeRewards, 9 ) == 5 );
      const auto variable = count( current, 4551 ) - count( beforeRewards, 4551 );
      return current.exp == beforeRewards.exp + baseExp && firstPool &&
             count( current, 5016 ) - count( beforeRewards, 5016 ) == 1 && count( current, 12728 ) - count( beforeRewards, 12728 ) == 1 &&
             variable >= 1 && variable <= 3;
    };
    const auto rewarded = fighter.waitState( receivedKillRewards, "received defeat EXP and delayed loot", 15 );
    const auto afterRewards = Bot::rewardValues( rewarded, workIndex );
    const auto afterInventory = rewarded.at( "rewards" ).at( "inventory" );
    const auto delta = combatRewardDelta( beforeRewards, afterRewards, baseExp );
    std::string loot;
    for( const auto& [ item, quantity ] : delta )
      loot += " " + std::to_string( item ) + "x" + std::to_string( quantity );
    ctx.log( "defeat rewards: +" + std::to_string( baseExp ) + " EXP, loot" + loot );
    for( Bot* bot : { &fighter, &observer } )
      bot->waitState( [ & ]( const Json& s ) { return Bot::actor( s, target ) == nullptr; }, "defeated target removed after server fade", 20 );

    // A fresh login supplies the authoritative inventory/EXP and proves
    // persistence; the kill-time deltas are not treated as that proof.
    fighter.close();
    observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, entity ) == nullptr; }, "fighter disconnect", 30 );
    auto& reloaded = ctx.spawn( "fighter-reloaded" );
    reloaded.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
    const auto persisted = reloaded.expectRewards( afterRewards, workIndex );
    expect( persisted.at( "rewards" ).at( "inventory" ) == afterInventory, "the inventory persisted across a fresh login" );
    expect( persisted.at( "gm_rank" ) == 0 && persisted.at( "territory" ) == CentralThanalan::Territory, "the reloaded fighter is a non-GM in Central Thanalan" );
    reloaded.logout();
    observer.logout();
  }
};

EXPOSE_SCENARIO( FastBlade );
