// The level-one caster action: a Thaumaturge casts Blizzard at a natural marmot
// within independently observed spell range, using received MP; both clients
// see the committed damage, the caster its own integrity and action start.
#include "../../harness/Combat.h"
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"

using namespace Sapphire::E2E;

class Blizzard : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto blizzard = actionMeta( data, 142 );
    expect( blizzard == Json{ { "action", 142 }, { "class_job", 7 }, { "work_index", 5 }, { "level", 1 }, { "base_exp", 50 },
                              { "category", 2 }, { "cost_type", 3 }, { "cost", 4 }, { "range", 25 }, { "cast_ms", 2500 },
                              { "recast_ms", 2500 }, { "recast_group", 58 }, { "effect_type", 1 }, { "target_enemy", true } },
            "Blizzard metadata matches the supported level-one profile: " + blizzard.dump() );

    const auto spawn = population( ctx, CentralThanalan::Territory ).spawn( CentralThanalan::BlizzardMarmotSpawn );
    expect( spawn.baseId == CentralThanalan::Marmot && spawn.level == 1, "the marmot spawn is a level-one population" );
    data.navi( CentralThanalan::Territory );

    CharacterOptions options;
    options.territory = CentralThanalan::Territory;
    options.position = beside( spawn.position );
    options.classJob = 7;
    auto& caster = ctx.spawnCharacter( "thaumaturge-caster", options );
    options.classJob = 1;
    auto& witness = ctx.spawnCharacter( "thaumaturge-witness", options );
    auto state = caster.snapshot();
    const auto entity = Bot::entity( state );
    expect( state.at( "rewards" ).at( "class_job" ) == blizzard.at( "class_job" ), "the fixture is a Thaumaturge" );

    state = caster.waitState( [ & ]( const Json& s ) {
      return !healthyEnemies( s, CentralThanalan::Marmot, 1, 20.0 ).empty() && Bot::actor( s, entity )->at( "mp" ).get< int >() >= 4;
    }, "natural target and received Thaumaturge MP (respawn takes 15s)", 60 );
    const auto nearest = healthyEnemies( state, CentralThanalan::Marmot, 1, 20.0 ).front();
    const uint32_t target = nearest.first;
    const Json before = nearest.second;
    const auto mpBefore = Bot::actor( state, entity )->at( "mp" ).get< int >();
    witness.waitState( [ & ]( const Json& s ) {
      const auto* enemy = Bot::actor( s, target );
      const auto* own = Bot::actor( s, entity );
      return enemy && own && enemy->at( "hp" ) == before.at( "hp" ) &&
             distance( enemy->at( "position" ).get< Point >(), own->at( "position" ).get< Point >() ) < 25;
    }, "witness sees Thaumaturge and natural target within spell range", 20 );
    caster.waitActionReady( StarterAction::Blizzard, target );
    const auto effect = caster.action( StarterAction::Blizzard, target );
    expect( effect.at( "action" ) == 142 && damageValue( effect ) > 0, "Blizzard is a damaging effect" );
    for( Bot* bot : { &caster, &witness } )
      bot->waitState( [ & ]( const Json& s ) { return committedDamage( s, effect, before ); },
                      "Blizzard matching effect and committed HP", 10 );
    const auto after = caster.waitState( [ & ]( const Json& s ) {
      bool integrity = false, start = false;
      for( const auto& row : s.at( "combat" ).at( "integrities" ) )
        if( row.at( "target" ) == entity && row.at( "result" ) == effect.at( "result" ) && row.at( "hp" ).get< int >() > 0 ) integrity = true;
      for( const auto& row : s.at( "combat" ).at( "starts" ) )
        if( row.at( "source" ) == entity && row.at( "action" ) == 142 && row.at( "group" ) == 58 && row.at( "recast_centiseconds" ) == 250 ) start = true;
      return integrity && start;
    }, "received Blizzard source integrity and action start", 10 );
    Json integrity;
    for( const auto& row : after.at( "combat" ).at( "integrities" ) )
      if( row.at( "target" ) == entity && row.at( "result" ) == effect.at( "result" ) ) integrity = row;
    ctx.log( "Blizzard dealt " + std::to_string( damageValue( effect ) ) + "; caster MP " + std::to_string( mpBefore ) + " -> " +
             std::to_string( integrity.at( "mp" ).get< int >() ) );
    caster.logout();
    witness.logout();
  }
};

EXPOSE_SCENARIO( Blizzard );
