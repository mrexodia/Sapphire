// The other level-one melee starter: a Pugilist walks up to a natural marmot
// (every reached point witnessed) and lands one Bootshine whose damage both
// clients see committed. No granted class, resources or skills.
#include "../../harness/Combat.h"
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"

using namespace Sapphire::E2E;

class Bootshine : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto bootshine = actionMeta( data, 53 );
    expect( bootshine == Json{ { "action", 53 }, { "class_job", 2 }, { "work_index", 0 }, { "level", 1 }, { "base_exp", 50 },
                               { "category", 3 }, { "cost_type", 5 }, { "cost", 60 }, { "range", -1 }, { "cast_ms", 0 },
                               { "recast_ms", 2500 }, { "recast_group", 58 }, { "effect_type", 1 }, { "target_enemy", true } },
            "Bootshine metadata matches the supported level-one profile: " + bootshine.dump() );

    const auto spawn = population( ctx, CentralThanalan::Territory ).spawn( CentralThanalan::BootshineMarmotSpawn );
    expect( spawn.baseId == CentralThanalan::Marmot && spawn.level == 1, "the marmot spawn is a level-one population" );
    data.navi( CentralThanalan::Territory );

    CharacterOptions options;
    options.territory = CentralThanalan::Territory;
    options.position = beside( spawn.position );
    options.classJob = 2;
    auto& pugilist = ctx.spawnCharacter( "pugilist-fighter", options );
    options.classJob = 1;
    auto& witness = ctx.spawnCharacter( "pugilist-witness", options );
    auto state = pugilist.snapshot();
    const auto entity = Bot::entity( state );
    expect( state.at( "rewards" ).at( "class_job" ) == bootshine.at( "class_job" ), "the fixture is a Pugilist" );
    expect( Bot::actor( state, entity )->at( "level" ) == bootshine.at( "level" ), "the fixture is level one" );

    // The population roams while other scenarios run. Approach with received
    // positions only, the witness confirming every reached point; never relocate
    // the enemy or inject movement.
    std::vector< Point > approach;
    bool reached = false;
    for( int leg = 0; leg < 6 && !reached; ++leg )
    {
      // Marmots respawn 15s after a kill; wait for one rather than failing.
      const auto nearby = waitHealthyEnemy( pugilist, CentralThanalan::Marmot, 1, 60.0, 90 );
      state = pugilist.snapshot();
      const auto position = nearby.second.at( "position" ).get< Point >();
      if( distance( position, Bot::predicted( state ) ) < 2 )
      {
        reached = true;
        break;
      }
      // The nearest healthy marmot may be well down the slope; walk at running
      // speed with time for a 60 m leg.
      const auto destination = beside( position );
      pugilist.walkTo( destination, 6.0f, 30 );
      witness.waitState( [ & ]( const Json& s ) {
        const auto* own = Bot::actor( s, entity );
        return own && distance( own->at( "position" ).get< Point >(), destination ) < 0.15;
      }, "witness sees bounded Pugilist approach", 30 );
      approach.push_back( destination );
    }
    expect( reached, "bounded Pugilist approach did not reach a natural target" );
    ctx.log( "approach took " + std::to_string( approach.size() ) + " witnessed legs" );

    state = pugilist.waitState( [ & ]( const Json& s ) {
      return !healthyEnemies( s, CentralThanalan::Marmot, 1, 2.0 ).empty() && Bot::actor( s, entity )->at( "tp" ).get< int >() >= 60;
    }, "nearby natural target and Pugilist TP", 30 );
    const auto chosen = healthyEnemies( state, CentralThanalan::Marmot, 1, 2.0 ).front();
    const uint32_t targetId = chosen.first;
    const Json targetBefore = chosen.second;
    witness.waitState( [ & ]( const Json& s ) {
      const auto* enemy = Bot::actor( s, targetId );
      return enemy && Bot::actor( s, entity ) && enemy->at( "hp" ) == targetBefore.at( "hp" );
    }, "witness sees Pugilist and target before Bootshine", 20 );
    pugilist.waitActionReady( StarterAction::Bootshine, targetId );
    const auto effect = pugilist.action( StarterAction::Bootshine, targetId );
    expect( effect.at( "action" ) == 53 && damageValue( effect ) > 0, "Bootshine is a damaging effect" );
    for( Bot* bot : { &pugilist, &witness } )
      bot->waitState( [ & ]( const Json& s ) { return committedDamage( s, effect, targetBefore ); },
                      "Bootshine matching effect and committed HP", 10 );
    const auto started = pugilist.waitState( [ & ]( const Json& s ) {
      for( const auto& row : s.at( "combat" ).at( "starts" ) )
        if( row.at( "source" ) == entity && row.at( "action" ) == 53 && row.at( "group" ) == 58 && row.at( "recast_centiseconds" ) == 250 )
          return true;
      return false;
    }, "received Bootshine action start", 10 );
    expect( started.at( "rewards" ).at( "class_job" ) == 2, "the Pugilist is still a Pugilist" );
    ctx.log( "Bootshine dealt " + std::to_string( damageValue( effect ) ) );
    pugilist.logout();
    witness.logout();
  }
};

EXPOSE_SCENARIO( Bootshine );
