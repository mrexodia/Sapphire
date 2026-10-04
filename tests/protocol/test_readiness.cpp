// Synthetic combat-readiness contracts (the former tests/e2e/test_combat_policy.py);
// not real gameplay or client compatibility.
#include "Readiness.h"
#include <iostream>
#include <string>

using namespace Sapphire::Testing;
using Json = nlohmann::json;

#define require( ok ) do { if( !( ok ) ) throw std::runtime_error( "readiness assertion failed at line " + std::to_string( __LINE__ ) ); } while( false )

namespace
{
  // The check must throw ReadinessError whose message contains `fragment`.
  template< class F >
  void rejects( F f, const std::string& fragment, int line )
  {
    try
    {
      f();
    }
    catch( const ReadinessError& error )
    {
      if( std::string( error.what() ).find( fragment ) == std::string::npos )
        throw std::runtime_error( "line " + std::to_string( line ) + ": unexpected message '" + error.what() + "'" );
      return;
    }
    throw std::runtime_error( "line " + std::to_string( line ) + ": expected a ReadinessError mentioning '" + fragment + "'" );
  }
#define REJECTS( expr, fragment ) rejects( [ & ] { ( void )( expr ); }, fragment, __LINE__ )

  Json readyState()
  {
    return { { "phase", "ready" }, { "entity_id", 7 }, { "gm_rank", 0 }, { "moving", false },
             { "event_id", nullptr }, { "scene", nullptr },
             { "rewards", { { "class_job", 1 }, { "level_by_index", { 1 } } } },
             { "predicted_position", { 0, 0, 0 } },
             { "combat", { { "starting_action_guard_remaining_ms", 0 }, { "effects", Json::array() }, { "integrities", Json::array() } } },
             { "actors", { { "7", { { "kind", 1 }, { "hp", 94 }, { "tp", 60 }, { "level", 1 } } },
                           { "8", { { "kind", 2 }, { "level", 1 }, { "hp", 94 }, { "position", { 0, 0, 2 } } } } } } };
  }

  bool fastBladeReady( const Json& s, uint32_t target ) { return actionReady( s, 9, target ); }
  bool savageBladeReady( const Json& s, uint32_t target ) { return actionReady( s, 11, target ); }
  bool bootshineReady( const Json& s, uint32_t target ) { return actionReady( s, 53, target ); }
  bool trueStrikeReady( const Json& s, uint32_t target ) { return actionReady( s, 54, target ); }
  bool blizzardReady( const Json& s, uint32_t target ) { return actionReady( s, 142, target ); }

  struct Hit
  {
    Json state, effect, before;
  };

  Hit exampleHit()
  {
    Json effect{ { "source", 7 }, { "target", 8 }, { "action", 9 }, { "kind", 1 }, { "request", 1 }, { "result", 42 },
                 { "effects", { { { "type", 3 }, { "flag", 0 }, { "value", 9 }, { "args", { 0, 0, 0 } } } } } };
    Json integrity{ { "target", 8 }, { "result", 42 }, { "hp", 85 }, { "hp_max", 94 }, { "mp", 0 }, { "tp", 1000 } };
    auto state = readyState();
    state[ "combat" ][ "effects" ] = Json::array( { effect } );
    state[ "combat" ][ "integrities" ] = Json::array( { integrity } );
    return { state, effect, Json{ { "hp", 94 }, { "hp_max", 94 } } };
  }
}

int main()
{
  try
  {
    // Sprint readiness requires a received living player with TP.
    {
      auto state = readyState();
      require( sprintReady( state ) );
      state[ "actors" ][ "7" ][ "tp" ] = 49;
      require( !sprintReady( state ) );
      state[ "actors" ][ "7" ][ "tp" ] = 50;
      state[ "combat" ][ "starting_action_guard_remaining_ms" ] = 1;
      require( !sprintReady( state ) );
      state[ "actors" ][ "7" ][ "kind" ] = 2;
      REJECTS( sprintReady( state ), "defeated" );
    }

    // Readiness requires both the elapsed local guard and received resources.
    {
      auto state = readyState();
      require( fastBladeReady( state, 8 ) );
      state[ "combat" ][ "starting_action_guard_remaining_ms" ] = 1;
      require( !fastBladeReady( state, 8 ) );
      state[ "combat" ][ "starting_action_guard_remaining_ms" ] = 0;
      state[ "actors" ][ "7" ][ "tp" ] = 59;
      require( !fastBladeReady( state, 8 ) );
    }

    // A missing or invalid guard never defaults to ready.
    for( const Json value : { Json(), Json( true ), Json( -1 ), Json( 0.1 ) } )
    {
      auto state = readyState();
      state[ "combat" ][ "starting_action_guard_remaining_ms" ] = value;
      REJECTS( fastBladeReady( state, 8 ), "pacing guard" );
    }
    {
      auto state = readyState();
      state[ "combat" ].erase( "starting_action_guard_remaining_ms" );
      REJECTS( fastBladeReady( state, 8 ), "pacing guard" );
    }

    // An unobserved (zero) target id is rejected, not "not ready".
    REJECTS( fastBladeReady( readyState(), 0 ), "32-bit" );

    // A busy actor is never ready.
    {
      auto state = readyState(); state[ "phase" ] = "zoning"; require( !fastBladeReady( state, 8 ) );
      state = readyState(); state[ "moving" ] = true; require( !fastBladeReady( state, 8 ) );
      state = readyState(); state[ "scene" ] = Json::object(); require( !fastBladeReady( state, 8 ) );
      state = readyState(); state[ "event_id" ] = 99; require( !fastBladeReady( state, 8 ) );
    }

    // Profile, death and estimated-range guards.
    {
      auto state = readyState();
      require( !fastBladeReady( state, 9 ) );
      state[ "actors" ][ "8" ][ "position" ][ 2 ] = 2.51;
      require( !fastBladeReady( state, 8 ) );
      state[ "actors" ][ "8" ][ "position" ][ 2 ] = "nan";
      REJECTS( fastBladeReady( state, 8 ), "position" );
      state = readyState();
      state[ "actors" ][ "8" ][ "kind" ] = 1;
      require( !fastBladeReady( state, 8 ) );
      state = readyState();
      state[ "actors" ][ "8" ][ "hp" ] = 0;
      require( !fastBladeReady( state, 8 ) );
      state = readyState();
      state[ "actors" ][ "8" ][ "level" ] = 14;
      require( fastBladeReady( state, 8 ) );
      state = readyState();
      state[ "actors" ][ "7" ][ "hp" ] = 0;
      REJECTS( fastBladeReady( state, 8 ), "defeated" );
      state = readyState();
      state[ "gm_rank" ] = 1;
      REJECTS( fastBladeReady( state, 8 ), "non-GM" );
      state = readyState();
      state[ "rewards" ][ "class_job" ] = 2;
      REJECTS( fastBladeReady( state, 8 ), "Gladiator" );
    }

    // Savage Blade needs level 4 and the exact received combo marker.
    {
      auto state = readyState();
      state[ "rewards" ][ "level_by_index" ] = { 0, 4 };
      state[ "actors" ][ "7" ][ "level" ] = 4;
      state[ "combat" ][ "effects" ] = Json::array( { Json{ { "source", 7 }, { "target", 8 }, { "action", 9 },
        { "source_effects", { { { "type", 29 }, { "value", 9 }, { "flag", 0x80 }, { "args", { 0, 0, 0 } } } } } } } );
      require( savageBladeReady( state, 8 ) );
      state[ "combat" ][ "effects" ][ 0 ][ "source_effects" ][ 0 ][ "value" ] = 10;
      require( !savageBladeReady( state, 8 ) );
      state[ "combat" ][ "effects" ][ 0 ][ "source_effects" ][ 0 ][ "value" ] = 9;
      state[ "rewards" ][ "level_by_index" ][ 1 ] = 3;
      REJECTS( savageBladeReady( state, 8 ), "level 4" );
    }

    // Bootshine needs a received Pugilist.
    {
      auto state = readyState();
      state[ "rewards" ][ "class_job" ] = 2;
      require( bootshineReady( state, 8 ) );
      state[ "rewards" ][ "class_job" ] = 1;
      REJECTS( bootshineReady( state, 8 ), "Pugilist" );
    }

    // True Strike needs a received level-two Pugilist with 50 TP.
    {
      auto state = readyState();
      state[ "rewards" ][ "class_job" ] = 2;
      state[ "rewards" ][ "level_by_index" ] = { 2 };
      state[ "actors" ][ "7" ][ "level" ] = 2;
      state[ "actors" ][ "7" ][ "tp" ] = 50;
      require( trueStrikeReady( state, 8 ) );
      state[ "actors" ][ "7" ][ "tp" ] = 49;
      require( !trueStrikeReady( state, 8 ) );
      state[ "actors" ][ "7" ][ "tp" ] = 50;
      state[ "rewards" ][ "level_by_index" ][ 0 ] = 1;
      REJECTS( trueStrikeReady( state, 8 ), "level 2" );
      state[ "rewards" ][ "level_by_index" ][ 0 ] = 2;
      state[ "actors" ][ "7" ][ "level" ] = 1;
      REJECTS( trueStrikeReady( state, 8 ), "actor level" );
    }

    // Blizzard needs a received Thaumaturge with MP in range.
    {
      auto state = readyState();
      state[ "rewards" ][ "class_job" ] = 7;
      state[ "actors" ][ "7" ][ "mp" ] = 4;
      state[ "actors" ][ "8" ][ "position" ] = { 0, 0, 24 };
      require( blizzardReady( state, 8 ) );
      state[ "actors" ][ "7" ][ "mp" ] = 3;
      require( !blizzardReady( state, 8 ) );
      state[ "actors" ][ "7" ][ "mp" ] = 4;
      state[ "actors" ][ "8" ][ "position" ] = { 0, 0, 24.6 };
      require( !blizzardReady( state, 8 ) );
      state[ "rewards" ][ "class_job" ] = 1;
      REJECTS( blizzardReady( state, 8 ), "Thaumaturge" );
    }

    // An effect alone, or a snapshot HP, is not committed damage.
    {
      auto hit = exampleHit();
      require( damageValue( hit.effect ) == 9 && committedDamage( hit.state, hit.effect, hit.before ) );
      hit.state[ "combat" ][ "integrities" ] = Json::array();
      hit.state[ "actors" ][ "8" ][ "hp" ] = 85;
      require( !committedDamage( hit.state, hit.effect, hit.before ) );
      hit = exampleHit();
      hit.state[ "combat" ][ "effects" ] = Json::array();
      require( !committedDamage( hit.state, hit.effect, hit.before ) );
    }

    // The observer must receive the identical action, not a stale or unrelated hit.
    for( const auto& [ key, value ] : std::vector< std::pair< std::string, Json > >{
           { "source", 10 }, { "target", 10 }, { "action", 7 }, { "request", 2 }, { "result", 43 }, { "kind", 2 }, { "effects", Json::array() } } )
    {
      auto hit = exampleHit();
      hit.state[ "combat" ][ "effects" ][ 0 ][ key ] = value;
      require( !committedDamage( hit.state, hit.effect, hit.before ) );
    }

    // The integrity must match target, result and the exact pre-hit delta.
    for( const auto& [ key, value ] : std::vector< std::pair< std::string, Json > >{
           { "target", 7 }, { "result", 43 }, { "hp", 84 }, { "hp_max", 95 } } )
    {
      auto hit = exampleHit();
      hit.state[ "combat" ][ "integrities" ][ 0 ][ key ] = value;
      require( !committedDamage( hit.state, hit.effect, hit.before ) );
    }

    // Retaliation uses independent pre-hit health.
    {
      auto hit = exampleHit();
      hit.effect[ "source" ] = 8; hit.effect[ "target" ] = 7; hit.effect[ "action" ] = 7; hit.effect[ "request" ] = 0;
      hit.state[ "combat" ][ "effects" ] = Json::array( { hit.effect } );
      hit.state[ "combat" ][ "integrities" ][ 0 ][ "target" ] = 7;
      require( committedDamage( hit.state, hit.effect, hit.before ) );
      require( !committedDamage( hit.state, hit.effect, Json{ { "hp", 93 }, { "hp_max", 94 } } ) );
      hit.effect[ "effects" ][ 0 ][ "flag" ] = 1;
      hit.state[ "combat" ][ "effects" ] = Json::array( { hit.effect } );
      require( damageValue( hit.effect ) == 0 && !committedDamage( hit.state, hit.effect, hit.before ) );
    }

    // A wait sees the predicate flip without the check sending or retrying anything.
    {
      std::vector< Json > states{ readyState(), readyState(), readyState() };
      states[ 0 ][ "combat" ][ "starting_action_guard_remaining_ms" ] = 1;
      states[ 1 ][ "actors" ][ "7" ][ "tp" ] = 59;
      std::vector< bool > results;
      for( const auto& s : states )
        results.push_back( fastBladeReady( s, 8 ) );
      require( ( results == std::vector< bool >{ false, false, true } ) );
    }
  }
  catch( const std::exception& error )
  {
    std::cerr << error.what() << '\n';
    return 1;
  }
  std::cout << "readiness contracts hold\n";
  return 0;
}
