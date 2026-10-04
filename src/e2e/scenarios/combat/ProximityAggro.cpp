// Natural vision aggro without a player action: a level-one player walks from
// outside a level-six active-vision enemy's sense range into it and never acts.
// The enemy attacks on its own, a witness receives the identical committed hit,
// the enemy defeats the player, and the homepoint return leaves EXP, level,
// currency and inventory untouched.
#include "../../harness/Combat.h"
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"

using namespace Sapphire::E2E;

class ProximityAggro : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto enemy = population( ctx, CentralThanalan::Territory ).spawn( CentralThanalan::ProximitySpawn );
    expect( enemy.baseId == CentralThanalan::ProximityEnemy && enemy.level == 6, "the spawn is the level-six active-vision enemy" );
    expect( enemy.activeType == 0, "the enemy is an active (aggressive) population" );
    expect( enemy.sense == std::array< int, 2 >{ 1, 0 } && enemy.senseRange == std::array< int, 2 >{ 14, 10 },
            "the enemy senses by vision over 14m" );
    expect( enemy.wanderingRange == 6 && !enemy.nonpop && !enemy.invalidRepop, "the enemy wanders 6m and respawns normally" );
    expect( distance( enemy.position, { 47.837039947509766f, 20.88382911682129f, -297.4685974121094f } ) < 0.001 &&
            std::abs( enemy.rotation - 0.26782724261283875f ) < 1e-6, "the population record is the bound one" );
    data.navi( CentralThanalan::Territory );
    const auto approach = proximityApproach( data, CentralThanalan::Territory, enemy );
    const auto& route = approach.route.points;
    const auto home = homepoint( data, Homepoints::Uldah );
    expect( home.territory == Uldah::Territory, "homepoint 9 returns to Ul'dah" );
    ctx.log( "approach route " + std::to_string( route.size() ) + " points, " + std::to_string( approach.route.length ).substr( 0, 5 ) +
             "m; witness " + std::to_string( horizontal( approach.witness, enemy.position ) ).substr( 0, 4 ) + "m from the enemy" );

    CharacterOptions witnessOptions;
    witnessOptions.territory = CentralThanalan::Territory;
    witnessOptions.position = approach.witness;
    auto& witness = ctx.spawnCharacter( "proximity-aggro-witness", witnessOptions );
    CharacterOptions fighterOptions;
    fighterOptions.territory = CentralThanalan::Territory;
    fighterOptions.position = route.front();
    auto& fighter = ctx.spawnCharacter( "proximity-aggro-fighter", fighterOptions );
    const auto initial = waitRewardsObserved( fighter, 1 );
    const auto entity = Bot::entity( initial );
    const Json before = *Bot::actor( initial, entity );
    const auto beforeRewards = Bot::rewardValues( initial, 1 );
    const auto beforeInventory = initial.at( "rewards" ).at( "inventory" );
    expect( before.at( "hp" ) == before.at( "hp_max" ) && before.at( "hp" ).get< int >() > 0 && before.at( "level" ) == 1,
            "the fighter is a full-health level-one player" );

    auto bound = [ & ]( const Json& actor ) {
      return actor.at( "layout_id" ) == enemy.layoutId && actor.at( "base_id" ) == enemy.baseId && actor.at( "level" ) == enemy.level &&
             actor.at( "hp" ).get< int64_t >() > 0 && actor.at( "hp" ) == actor.at( "hp_max" );
    };
    const auto state = fighter.waitState( [ & ]( const Json& s ) {
      for( const auto& [ key, actor ] : s.at( "actors" ).items() )
        if( bound( actor ) ) return true;
      return false;
    }, "source-bound living active-vision enemy (allow one respawn)", enemy.popInterval + 30 );
    uint32_t target = 0;
    for( const auto& [ key, actor ] : state.at( "actors" ).items() )
      if( bound( actor ) ) { target = static_cast< uint32_t >( std::stoul( key ) ); break; }
    const auto witnessBefore = witness.waitState( [ & ]( const Json& s ) { return Bot::actor( s, entity ) && Bot::actor( s, target ); },
                                                  "witness independently receives fighter and active enemy", 20 );
    expect( distance( Bot::predicted( state ), enemy.position ) > 15, "the fighter starts outside the enemy's sense range" );
    expect( state.at( "combat" ).at( "effects" ).empty() && state.at( "combat" ).at( "starts" ).empty(), "no combat before the approach" );

    fighter.walkRoute( route, 6.0f, 30 );
    witness.waitState( [ & ]( const Json& s ) {
      const auto* own = Bot::actor( s, entity );
      return own && distance( own->at( "position" ).get< Point >(), route.back() ) < 0.15;
    }, "witness sees source-navmesh vision approach", 30 );
    auto unprovoked = [ & ]( const Json& row ) {
      return row.at( "source" ) == target && row.at( "target" ) == entity && row.at( "kind" ) == 1 && damageValue( row ) > 0;
    };
    const auto first = fighter.waitState( [ & ]( const Json& s ) {
      for( const auto& row : s.at( "combat" ).at( "effects" ) )
        if( unprovoked( row ) && committedDamage( s, row, before ) ) return true;
      return false;
    }, "natural active enemy attacks without a player action", 30 );
    Json effect;
    for( const auto& row : first.at( "combat" ).at( "effects" ) )
      if( unprovoked( row ) ) { effect = row; break; }
    expect( first.at( "combat" ).at( "starts" ).empty(), "the player never started an action" );
    for( const auto& row : first.at( "combat" ).at( "effects" ) )
      expect( row.at( "source" ) != entity, "the player never produced an effect" );
    expect( committedDamage( first, effect, before ), "the first unprovoked hit is committed against full health" );
    Json firstIntegrity;
    for( const auto& row : first.at( "combat" ).at( "integrities" ) )
      if( row.at( "target" ) == entity && row.at( "result" ) == effect.at( "result" ) ) firstIntegrity = row;
    ctx.log( "first unprovoked hit " + std::to_string( damageValue( effect ) ) + " -> HP " + firstIntegrity.at( "hp" ).dump() );

    const Json witnessView = *Bot::actor( witnessBefore, entity );
    const auto witnessed = witness.waitState( [ & ]( const Json& s ) { return committedDamage( s, effect, witnessView ); },
                                              "witness receives identical committed unprovoked enemy action", 20 );
    expect( committedDamage( witnessed, effect, witnessView ), "the witness holds the identical committed hit" );

    const auto defeated = fighter.waitState( [ & ]( const Json& s ) {
      const auto* own = Bot::actor( s, entity );
      return own && own->at( "hp" ) == 0;
    }, "natural active enemy defeats non-attacking player", 240 );
    const auto observedDefeat = witness.waitState( [ & ]( const Json& s ) {
      const auto* own = Bot::actor( s, entity );
      return own && own->at( "hp" ) == 0;
    }, "witness sees unprovoked natural player defeat", 20 );
    expect( Bot::actor( observedDefeat, entity )->at( "hp" ) == 0, "the witness sees the fighter at zero HP" );
    expect( defeated.at( "combat" ).at( "starts" ).empty(), "the player never started an action through the defeat" );
    for( const auto& row : defeated.at( "combat" ).at( "effects" ) )
      expect( row.at( "source" ) != entity, "the player never produced an effect through the defeat" );
    requireUnchangedDeathState( beforeRewards, beforeInventory, Bot::rewardValues( defeated, 1 ), defeated.at( "rewards" ).at( "inventory" ) );
    std::vector< Json > incoming;
    for( const auto& row : defeated.at( "combat" ).at( "effects" ) )
      if( unprovoked( row ) ) incoming.push_back( row );
    expect( !incoming.empty() && std::find( incoming.begin(), incoming.end(), effect ) != incoming.end(),
            "the defeat came from the bound enemy's hits including the first" );
    ctx.log( "defeated after " + std::to_string( incoming.size() ) + " hits from the enemy" );

    const auto returned = fighter.returnHomepoint( home.territory, home.popRange.position );
    witness.waitState( [ & ]( const Json& s ) { return Bot::actor( s, entity ) == nullptr; }, "unprovoked defeated fighter leaves source territory", 30 );
    requireUnchangedDeathState( beforeRewards, beforeInventory, Bot::rewardValues( returned, 1 ), returned.at( "rewards" ).at( "inventory" ) );
    fighter.logout();
    witness.logout();
  }
};

EXPOSE_SCENARIO( ProximityAggro );
