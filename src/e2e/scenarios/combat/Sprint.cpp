// Sprint as a received status and TP debit: the player's own effect, the same
// effect at an observer, the zero-TP HUD commit and the recast metadata. No
// granted resources; the player waits for its naturally regenerated TP.
#include "../../harness/Combat.h"
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"

using namespace Sapphire::E2E;

class Sprint : public Scenario
{
  void run( Context& ctx ) override
  {
    const auto sprint = actionMeta( ctx.data(), 3 );
    expect( sprint == Json{ { "action", 3 }, { "base_exp", 45 }, { "cast_ms", 0 }, { "category", 0 }, { "class_job", 0 },
                            { "cost", 0 }, { "cost_type", 18 }, { "effect_type", 1 }, { "level", 0 }, { "range", 0 },
                            { "recast_group", 56 }, { "recast_ms", 30000 }, { "target_enemy", false }, { "work_index", -1 } },
            "Sprint metadata matches the supported level-zero profile: " + sprint.dump() );

    auto& player = ctx.spawnCharacter( "sprinter" );
    auto& observer = ctx.spawnCharacter( "sprint-observer" );
    const auto entity = Bot::entity( player.snapshot() );
    observer.waitState( [ & ]( const Json& s ) {
      const auto* actor = Bot::actor( s, entity );
      return actor && actor->at( "kind" ) == 1;
    }, "observer received exact Sprint actor" );

    const auto ready = player.waitSprintReady();
    expect( Bot::actor( ready, entity )->at( "tp" ).get< int >() >= 50, "Sprint readiness carries at least 50 TP" );
    const auto acted = player.sprint();
    const auto request = acted.request;

    auto matching = [ & ]( const Json& s ) {
      std::vector< Json > rows;
      for( const auto& row : s.at( "combat" ).at( "effects" ) )
        if( row.at( "source" ) == entity && row.at( "target" ) == entity && row.at( "action" ) == 3 &&
            row.at( "kind" ) == 1 && row.at( "request" ) == request )
          rows.push_back( row );
      return rows;
    };
    Json exactEffect;
    for( Bot* bot : { &player, &observer } )
    {
      const auto observed = bot->waitState( [ & ]( const Json& s ) { return matching( s ).size() == 1; },
                                            "one exact independently received Sprint effect" );
      const auto effect = matching( observed ).front();
      expect( effect.at( "effects" ) == Json::array( { Json{ { "type", 18 }, { "value", 50 }, { "flag", 128 }, { "args", { 0, 0, 30 } } } } ),
              bot->name() + ": Sprint effect is the 30s status with the 50 TP debit: " + effect.dump() );
      if( exactEffect.is_null() )
        exactEffect = effect;
      else
        expect( effect == exactEffect, "observer received the identical Sprint effect" );
      const auto zeroTp = bot->waitState( [ & ]( const Json& s ) {
        for( const auto& row : s.at( "combat" ).at( "hud_params" ) )
          if( row.at( "target" ) == entity && row.at( "tp" ) == 0 ) return true;
        return false;
      }, "independently received zero-TP Sprint commit" );
      expect( zeroTp.at( "phase" ) == "ready" && zeroTp.at( "gm_rank" ) == 0, bot->name() + " stays a ready non-GM player" );
    }

    const auto started = player.waitState( [ & ]( const Json& s ) {
      for( const auto& row : s.at( "combat" ).at( "starts" ) )
        if( row.at( "source" ) == entity && row.at( "action" ) == 3 ) return true;
      return false;
    }, "received Sprint start metadata" );
    Json start;
    const auto& starts = started.at( "combat" ).at( "starts" );
    for( auto it = starts.rbegin(); it != starts.rend(); ++it )
      if( it->at( "source" ) == entity && it->at( "action" ) == 3 ) { start = *it; break; }
    expect( start.at( "group" ) == sprint.at( "recast_group" ), "Sprint start carries the Action sheet's recast group" );
    expect( start.at( "recast_centiseconds" ) == sprint.at( "recast_ms" ).get< uint32_t >() / 10, "Sprint start carries the 30s recast" );
    expect( acted.state.at( "phase" ) == "ready", "the player is ready after Sprint" );
    ctx.log( "Sprint effect " + exactEffect.dump() );
  }
};

EXPOSE_SCENARIO( Sprint );
