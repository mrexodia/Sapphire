// Four level-one Gladiators share the hate of a natural level-14 enemy and
// defeat it while a fifth bot only watches: every client sees every hit and
// its committed HP, each attacker receives the fixed EXP and delayed loot, the
// witness receives nothing, and the rewards survive a fresh login.
#include "../../harness/Combat.h"
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"
#include <set>

using namespace Sapphire::E2E;

class HighLevelMultiAttacker : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const uint32_t baseExp = enemyBaseExp( data, 14 );
    expect( baseExp == 115, "a level-14 enemy grants 115 EXP" );
    const auto spawn = population( ctx, CentralThanalan::Territory ).spawn( CentralThanalan::LevelFourteenSpawn );
    expect( spawn.baseId == CentralThanalan::LevelFourteenEnemy && spawn.level == 14 && !spawn.nonpop,
            "the level-14 spawn is an ordinary population of the expected kind" );
    data.navi( CentralThanalan::Territory );

    CharacterOptions options;
    options.territory = CentralThanalan::Territory;
    options.position = beside( spawn.position );
    std::vector< Bot* > fighters;
    std::vector< Fixture > fixtures;
    for( int index = 0; index < 4; ++index )
    {
      fighters.push_back( &ctx.spawnCharacter( "high-level-fighter-" + std::to_string( index ), options ) );
      fixtures.push_back( ctx.fixture( *fighters.back() ) );
    }
    auto& witness = ctx.spawnCharacter( "high-level-witness", options );
    std::vector< Bot* > all = fighters;
    all.push_back( &witness );
    std::vector< uint32_t > entities;
    for( Bot* bot : all )
      entities.push_back( Bot::entity( bot->snapshot() ) );
    for( Bot* bot : all )
      bot->waitState( [ & ]( const Json& s ) {
        for( const auto entity : entities )
          if( !Bot::actor( s, entity ) ) return false;
        return true;
      }, "all ordinary clients visible", 30 );

    const auto chosen = chooseAndApproach( all, witness, CentralThanalan::LevelFourteenEnemy, 14 );
    const uint32_t target = chosen.first;
    const Json targetBefore = chosen.second;
    expect( targetBefore.at( "hp" ) == targetBefore.at( "hp_max" ) && targetBefore.at( "hp" ) == 237, "the level-14 enemy starts at its 237 HP" );
    ctx.log( "fighting " + std::to_string( target ) + " (layout " + targetBefore.at( "layout_id" ).dump() + ")" );
    std::map< std::string, Bot::Rewards > beforeRewards;
    for( Bot* bot : all )
      beforeRewards[ bot->name() ] = Bot::rewardValues( waitRewardsObserved( *bot, 1 ), 1 );

    const auto hits = defeatWithFastBlades( ctx, fighters, all, target, targetBefore.at( "hp" ).get< int64_t >() );
    std::set< size_t > attackers;
    for( const auto& hit : hits )
      attackers.insert( hit.fighter );
    expect( attackers.size() == fighters.size(), "every fighter landed at least one hit" );

    std::map< std::string, Bot::Rewards > afterRewards;
    std::map< std::string, Json > inventories;
    for( Bot* fighter : fighters )
    {
      const auto& before = beforeRewards.at( fighter->name() );
      const auto rewarded = fighter->waitState( [ & ]( const Json& s ) {
        return s.at( "rewards" ).at( "inventory_ready" ).get< bool >() && s.at( "rewards" ).at( "exp_by_index" ).size() > 1 &&
               combatRewardMatches( before, Bot::rewardValues( s, 1 ), baseExp );
      }, "exact high-level EXP and delayed loot", 20 );
      const auto after = Bot::rewardValues( rewarded, 1 );
      combatRewardDelta( before, after, baseExp );
      afterRewards[ fighter->name() ] = after;
      inventories[ fighter->name() ] = rewarded.at( "rewards" ).at( "inventory" );
    }
    expect( Bot::rewardValues( witness.snapshot(), 1 ) == beforeRewards.at( witness.name() ), "the non-attacking witness earned nothing" );
    for( Bot* bot : all )
      bot->waitState( [ & ]( const Json& s ) { return Bot::actor( s, target ) == nullptr; }, "high-level target removed after natural defeat", 20 );
    for( Bot* bot : all )
      bot->logout( 10, true );

    for( size_t index = 0; index < fixtures.size(); ++index )
    {
      auto& reloaded = ctx.spawn( "high-level-reloaded-" + std::to_string( index ) );
      reloaded.loginViaLobby( ctx.server().relogin( fixtures[ index ] ), fixtures[ index ].name );
      const auto state = waitRewardsObserved( reloaded, 1 );
      const auto& name = fighters[ index ]->name();
      expect( Bot::rewardValues( state, 1 ) == afterRewards.at( name ), name + ": rewards persisted across a fresh login" );
      expect( state.at( "rewards" ).at( "inventory" ) == inventories.at( name ), name + ": inventory persisted across a fresh login" );
      reloaded.logout( 10, true );
    }
  }
};

EXPOSE_SCENARIO( HighLevelMultiAttacker );
