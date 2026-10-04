// Natural level-two progression: a Pugilist defeats six level-one marmots over
// six sessions (50 EXP each, the sixth kill crossing the 300 EXP threshold),
// every kill witnessed and every session starting from persisted state, then
// at level two lands Bootshine and the newly available True Strike. No EXP,
// level, skill or enemy grants.
#include "../../harness/Combat.h"
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"
#include <optional>

using namespace Sapphire::E2E;

class LevelTwoTrueStrike : public Scenario
{
  struct Approach
  {
    uint32_t target = 0;
    std::vector< Point > reached;
  };

  // Walk to the nearest healthy marmot with received positions, the witness
  // confirming every reached point. Marmots respawn 15s after a kill, so wait
  // for one rather than failing.
  static Approach approach( Bot& player, Bot& observer, uint32_t entity )
  {
    Approach result;
    for( int leg = 0; leg < 6; ++leg )
    {
      const auto nearest = waitHealthyEnemy( player, CentralThanalan::Marmot, 1, 20.0, 45 );
      const auto state = player.snapshot();
      const auto position = nearest.second.at( "position" ).get< Point >();
      if( distance( position, Bot::predicted( state ) ) < 2 )
      {
        result.target = nearest.first;
        return result;
      }
      const auto destination = beside( position );
      player.walkTo( destination, 2.0f, 15 );
      observer.waitState( [ & ]( const Json& s ) {
        const auto* own = Bot::actor( s, entity );
        return own && distance( own->at( "position" ).get< Point >(), destination ) < 0.15;
      }, "witness sees bounded progression approach", 15 );
      result.reached.push_back( destination );
    }
    throw Failure( "bounded progression approach did not reach a natural target" );
  }

  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto bootshine = actionMeta( data, 53 );
    const auto trueStrike = actionMeta( data, 54 );
    expect( trueStrike == Json{ { "action", 54 }, { "class_job", 2 }, { "work_index", 0 }, { "level", 2 }, { "base_exp", 55 },
                                { "category", 3 }, { "cost_type", 5 }, { "cost", 50 }, { "range", -1 }, { "cast_ms", 0 },
                                { "recast_ms", 2500 }, { "recast_group", 58 }, { "effect_type", 1 }, { "target_enemy", true } },
            "True Strike metadata matches the supported level-two profile: " + trueStrike.dump() );
    expect( bootshine.at( "class_job" ) == 2 && trueStrike.at( "class_job" ) == 2, "both actions are Pugilist actions" );
    expect( bootshine.at( "work_index" ) == 0 && trueStrike.at( "work_index" ) == 0, "the Pugilist EXP row is index 0" );
    expect( bootshine.at( "level" ) == 1 && trueStrike.at( "level" ) == 2, "Bootshine is level one, True Strike level two" );
    expect( bootshine.at( "base_exp" ) == 50 && trueStrike.at( "cost" ) == 50, "level-one enemies grant 50 EXP; True Strike costs 50 TP" );
    const uint32_t baseExp = bootshine.at( "base_exp" ).get< uint32_t >();

    const auto spawn = population( ctx, CentralThanalan::Territory ).spawn( CentralThanalan::BootshineMarmotSpawn );
    expect( spawn.baseId == CentralThanalan::Marmot && spawn.level == 1, "the marmot spawn is a level-one population" );
    data.navi( CentralThanalan::Territory );
    CharacterOptions options;
    options.territory = CentralThanalan::Territory;
    options.position = beside( spawn.position );
    options.classJob = 2;
    const auto fixture = ctx.server().freshCharacter( options );

    // After the sixth kill the received level/EXP are 2/0; fold them back onto the
    // "same level, +50 EXP" shape the reward contract is written for.
    auto completedReward = [ & ]( const Json& s, const Bot::Rewards& before, bool finalKill ) -> std::optional< Bot::Rewards > {
      if( !s.at( "rewards" ).at( "inventory_ready" ).get< bool >() || s.at( "rewards" ).at( "exp_by_index" ).empty() )
        return std::nullopt;
      auto normalized = Bot::rewardValues( s, 0 );
      if( finalKill )
      {
        if( !( before.level == 1 && before.exp == 250 && normalized.level == 2 && normalized.exp == 0 ) )
          return std::nullopt;
        normalized.level = 1;
        normalized.exp = 300;
      }
      return combatRewardMatches( before, normalized, baseExp ) ? std::optional( normalized ) : std::nullopt;
    };

    std::optional< Json > persistedInventory;
    for( int kill = 0; kill < 6; ++kill )
    {
      auto& player = ctx.spawn( "progression-fighter-" + std::to_string( kill ) );
      auto state = player.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
      const auto entity = Bot::entity( state );
      state = waitRewardsObserved( player, 0 );
      expect( state.at( "rewards" ).at( "class_job" ) == 2, "the fixture is a Pugilist" );
      expect( state.at( "rewards" ).at( "level_by_index" )[ 0 ] == 1 && state.at( "rewards" ).at( "exp_by_index" )[ 0 ] == kill * 50,
              "session " + std::to_string( kill + 1 ) + " starts at level 1 with " + std::to_string( kill * 50 ) + " EXP" );
      if( persistedInventory )
        expect( state.at( "rewards" ).at( "inventory" ) == *persistedInventory, "the inventory persisted across the relogin" );
      // Recovery is natural received regeneration, not fixture mutation.
      state = player.waitState( [ & ]( const Json& s ) {
        const auto* own = Bot::actor( s, entity );
        return own && own->at( "hp" ).get< int64_t >() > 0 && own->at( "hp" ) == own->at( "hp_max" );
      }, "naturally restored progression fighter", 60 );
      CharacterOptions witnessOptions;
      witnessOptions.territory = CentralThanalan::Territory;
      witnessOptions.position = Bot::position( state );
      auto& observer = ctx.spawnCharacter( "progression-witness-" + std::to_string( kill ), witnessOptions );
      observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, entity ) != nullptr; }, "witness sees progression fighter" );
      const auto approached = approach( player, observer, entity );
      const auto target = approached.target;
      const auto beforeRewards = Bot::rewardValues( player.snapshot(), 0 );
      std::vector< Json > effects;
      int64_t expectedHp = Bot::actor( player.snapshot(), target )->at( "hp" ).get< int64_t >();
      while( expectedHp > 0 )
      {
        expect( effects.size() < 16, "bounded Bootshine sequence did not defeat the natural target" );
        player.waitState( [ & ]( const Json& s ) {
          const auto* enemy = Bot::actor( s, target );
          return enemy && enemy->at( "hp" ).get< int64_t >() == expectedHp;
        }, "fighter receives exact committed Bootshine HP", 10 );
        approachTarget( player, target );
        const auto ready = player.waitActionReady( StarterAction::Bootshine, target, 45 );
        const Json before = *Bot::actor( ready, target );
        expect( before.at( "hp" ).get< int64_t >() == expectedHp && expectedHp > 0, "the fighter sees the exact pre-hit HP" );
        observer.waitState( [ & ]( const Json& s ) {
          const auto* enemy = Bot::actor( s, target );
          const auto* own = Bot::actor( s, entity );
          return enemy && own && enemy->at( "hp" ) == before.at( "hp" ) && own->at( "hp" ).get< int64_t >() > 0 &&
                 distance( enemy->at( "position" ).get< Point >(), own->at( "position" ).get< Point >() ) < 3;
        }, "witness sees exact progression pre-hit state", 10 );
        const auto effect = player.action( StarterAction::Bootshine, target );
        expect( effect.at( "action" ) == 53 && damageValue( effect ) > 0, "Bootshine is a damaging effect" );
        for( Bot* bot : { &player, &observer } )
          bot->waitState( [ & ]( const Json& s ) { return committedDamage( s, effect, before ); }, "witnessed Bootshine effect and committed HP", 10 );
        effects.push_back( effect );
        expectedHp = std::max< int64_t >( 0, before.at( "hp" ).get< int64_t >() - damageValue( effect ) );
      }

      const bool finalKill = kill == 5;
      const auto rewarded = player.waitState( [ & ]( const Json& s ) { return completedReward( s, beforeRewards, finalKill ).has_value(); },
                                              "exact natural progression EXP and delayed loot", 20 );
      const auto afterRewards = Bot::rewardValues( rewarded, 0 );
      combatRewardDelta( beforeRewards, *completedReward( rewarded, beforeRewards, finalKill ), baseExp );
      persistedInventory = rewarded.at( "rewards" ).at( "inventory" );
      for( Bot* bot : { &player, &observer } )
        bot->waitState( [ & ]( const Json& s ) { return Bot::actor( s, target ) == nullptr; }, "defeated progression target removed", 20 );
      ctx.log( "kill " + std::to_string( kill + 1 ) + ": " + std::to_string( effects.size() ) + " Bootshines after " +
               std::to_string( approached.reached.size() ) + " approach legs; level " + std::to_string( afterRewards.level ) + ", " +
               std::to_string( afterRewards.exp ) + " EXP" );
      player.logout( 10, true );
      observer.logout( 10, true );
    }

    auto& player = ctx.spawn( "level-two-pugilist" );
    auto state = player.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
    const auto entity = Bot::entity( state );
    state = waitRewardsObserved( player, 0 );
    expect( state.at( "rewards" ).at( "level_by_index" )[ 0 ] == 2 && state.at( "rewards" ).at( "exp_by_index" )[ 0 ] == 0,
            "the Pugilist is level 2 with 0 EXP after six kills" );
    expect( state.at( "rewards" ).at( "inventory" ) == *persistedInventory, "the inventory persisted into the level-two session" );
    state = player.waitState( [ & ]( const Json& s ) {
      const auto* own = Bot::actor( s, entity );
      return own && own->at( "hp" ).get< int64_t >() > 0 && own->at( "hp" ) == own->at( "hp_max" );
    }, "naturally restored level-two Pugilist", 60 );
    CharacterOptions witnessOptions;
    witnessOptions.territory = CentralThanalan::Territory;
    witnessOptions.position = Bot::position( state );
    auto& observer = ctx.spawnCharacter( "level-two-witness", witnessOptions );
    observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, entity ) != nullptr; }, "witness sees level-two Pugilist" );
    const auto target = approach( player, observer, entity ).target;

    auto ready = player.waitActionReady( StarterAction::Bootshine, target, 45 );
    const Json beforeBootshine = *Bot::actor( ready, target );
    observer.waitState( [ & ]( const Json& s ) {
      const auto* enemy = Bot::actor( s, target );
      return enemy && Bot::actor( s, entity ) && enemy->at( "hp" ) == beforeBootshine.at( "hp" );
    }, "witness sees level-two Bootshine pre-state", 10 );
    const auto bootshineEffect = player.action( StarterAction::Bootshine, target );
    for( Bot* bot : { &player, &observer } )
      bot->waitState( [ & ]( const Json& s ) { return committedDamage( s, bootshineEffect, beforeBootshine ); }, "level-two Bootshine committed HP", 10 );

    ready = player.waitActionReady( StarterAction::TrueStrike, target, 30 );
    const Json beforeTrueStrike = *Bot::actor( ready, target );
    expect( beforeTrueStrike.at( "hp" ).get< int64_t >() > 0 && Bot::actor( ready, entity )->at( "tp" ).get< int >() >= 50,
            "the target lives and the Pugilist has 50 TP for True Strike" );
    observer.waitState( [ & ]( const Json& s ) {
      const auto* enemy = Bot::actor( s, target );
      const auto* own = Bot::actor( s, entity );
      return enemy && own && enemy->at( "hp" ) == beforeTrueStrike.at( "hp" ) &&
             distance( enemy->at( "position" ).get< Point >(), own->at( "position" ).get< Point >() ) < 3;
    }, "witness sees exact True Strike pre-state", 10 );
    const auto trueStrikeEffect = player.action( StarterAction::TrueStrike, target );
    expect( trueStrikeEffect.at( "action" ) == 54 && damageValue( trueStrikeEffect ) > 0, "True Strike is a damaging effect" );
    for( Bot* bot : { &player, &observer } )
      bot->waitState( [ & ]( const Json& s ) { return committedDamage( s, trueStrikeEffect, beforeTrueStrike ); },
                      "identical True Strike effect and committed HP", 10 );
    const auto started = player.waitState( [ & ]( const Json& s ) {
      for( const auto& row : s.at( "combat" ).at( "starts" ) )
        if( row.at( "source" ) == entity && row.at( "action" ) == 54 && row.at( "group" ) == 58 && row.at( "recast_centiseconds" ) == 250 )
          return true;
      return false;
    }, "received True Strike action start", 10 );
    ctx.log( "True Strike dealt " + std::to_string( damageValue( trueStrikeEffect ) ) + " at level " +
             started.at( "rewards" ).at( "level_by_index" )[ 0 ].dump() + " with " + started.at( "rewards" ).at( "exp_by_index" )[ 0 ].dump() + " EXP" );
    player.logout( 10, true );
    observer.logout( 10, true );
  }
};

EXPOSE_SCENARIO( LevelTwoTrueStrike );
