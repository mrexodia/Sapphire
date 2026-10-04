#include "Readiness.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <string>

namespace Sapphire::Testing
{
  using Json = nlohmann::json;

  namespace
  {
    // The guard is the client's own conservative pacing; a missing or malformed
    // value must never read as "ready".
    int64_t guardRemaining( const Json& state, const char* what )
    {
      const auto& combat = state.at( "combat" );
      auto it = combat.find( "starting_action_guard_remaining_ms" );
      if( it == combat.end() || !it->is_number_integer() || it->get< int64_t >() < 0 )
        throw ReadinessError( std::string( "worker must expose the conservative " ) + what + " pacing guard" );
      return it->get< int64_t >();
    }

    bool idle( const Json& state )
    {
      return state.at( "phase" ) == "ready" && !state.at( "moving" ).get< bool >() &&
             state.at( "event_id" ).is_null() && state.at( "scene" ).is_null();
    }

    const Json* actor( const Json& state, uint32_t id )
    {
      const auto& actors = state.at( "actors" );
      auto it = actors.find( std::to_string( id ) );
      return it == actors.end() ? nullptr : &*it;
    }

    void requireTarget( uint32_t target )
    {
      if( target == 0 )
        throw ReadinessError( "combat target must be an observed 32-bit actor id" );
    }

    std::array< double, 3 > point( const Json& value )
    {
      if( !value.is_array() || value.size() != 3 )
        throw ReadinessError( "invalid estimated combat position" );
      std::array< double, 3 > out{};
      for( size_t i = 0; i < 3; ++i )
      {
        if( !value[ i ].is_number() || !std::isfinite( value[ i ].get< double >() ) )
          throw ReadinessError( "invalid estimated combat position" );
        out[ i ] = value[ i ].get< double >();
      }
      return out;
    }

    // Estimated request range only: the predicted own position against the
    // received enemy position. Observers establish actual range in a scenario.
    double estimatedDistance( const Json& state, const Json& enemy )
    {
      const auto own = point( state.at( "predicted_position" ) );
      const auto other = point( enemy.at( "position" ) );
      return std::sqrt( std::pow( own[ 0 ] - other[ 0 ], 2 ) + std::pow( own[ 1 ] - other[ 1 ], 2 ) +
                        std::pow( own[ 2 ] - other[ 2 ], 2 ) );
    }

    struct MeleeProfile
    {
      uint32_t classJob;
      const char* className;
      int64_t tpCost;
      int64_t minimumLevel;
      int workIndex;   // -1: no received-progression check
    };

    bool startingMeleeReady( const Json& state, uint32_t target, const MeleeProfile& profile )
    {
      requireTarget( target );
      const auto remaining = guardRemaining( state, "starting-melee" );
      if( !idle( state ) )
        return false;
      if( state.at( "gm_rank" ) != 0 || state.at( "rewards" ).at( "class_job" ) != profile.classJob )
        throw ReadinessError( std::string( "starting-melee readiness requires a non-GM " ) + profile.className );
      if( profile.workIndex >= 0 )
      {
        const auto& rewards = state.at( "rewards" );
        auto levels = rewards.find( "level_by_index" );
        if( levels == rewards.end() || !levels->is_array() || levels->size() <= static_cast< size_t >( profile.workIndex ) ||
            ( *levels )[ profile.workIndex ].get< int64_t >() < profile.minimumLevel )
          throw ReadinessError( std::string( profile.className ) + " action requires received level " +
                                std::to_string( profile.minimumLevel ) + " progression" );
      }
      const auto* own = actor( state, state.at( "entity_id" ).get< uint32_t >() );
      const auto* enemy = actor( state, target );
      if( !own || !enemy )
        return false;
      if( own->at( "hp" ).get< int64_t >() <= 0 )
        throw ReadinessError( "fighter was defeated while waiting for combat readiness" );
      if( enemy->at( "kind" ) != 2 || enemy->at( "hp" ).get< int64_t >() <= 0 )
        return false;
      const auto distance = estimatedDistance( state, *enemy );
      if( own->at( "level" ).get< int64_t >() < profile.minimumLevel )
        throw ReadinessError( std::string( profile.className ) + " actor level does not satisfy the source action" );
      return remaining == 0 && own->at( "tp" ).get< int64_t >() >= profile.tpCost && distance <= 2.5;
    }

    bool savageBladeReady( const Json& state, uint32_t target )
    {
      if( !startingMeleeReady( state, target, { 1, "Gladiator", 60, 4, 1 } ) )
        return false;
      // The latest own effect must be a Fast Blade on this target carrying the combo marker.
      const auto& effects = state.at( "combat" ).at( "effects" );
      const Json marker{ { "type", 29 }, { "value", 9 }, { "flag", 0x80 }, { "args", { 0, 0, 0 } } };
      for( auto it = effects.rbegin(); it != effects.rend(); ++it )
      {
        if( it->at( "source" ) != state.at( "entity_id" ) )
          continue;
        if( it->at( "target" ) != target || it->at( "action" ) != 9 )
          return false;
        const auto sourceEffects = it->value( "source_effects", Json::array() );
        return std::any_of( sourceEffects.begin(), sourceEffects.end(), [ & ]( const Json& e ) { return e == marker; } );
      }
      return false;
    }

    bool blizzardReady( const Json& state, uint32_t target )
    {
      requireTarget( target );
      const auto remaining = guardRemaining( state, "starting-action" );
      if( !idle( state ) )
        return false;
      if( state.at( "gm_rank" ) != 0 || state.at( "rewards" ).at( "class_job" ) != 7 )
        throw ReadinessError( "Blizzard readiness requires a non-GM Thaumaturge" );
      const auto* own = actor( state, state.at( "entity_id" ).get< uint32_t >() );
      const auto* enemy = actor( state, target );
      if( !own || !enemy )
        return false;
      if( own->at( "hp" ).get< int64_t >() <= 0 )
        throw ReadinessError( "caster was defeated while waiting for combat readiness" );
      if( enemy->at( "kind" ) != 2 || enemy->at( "hp" ).get< int64_t >() <= 0 )
        return false;
      const auto distance = estimatedDistance( state, *enemy );
      return remaining == 0 && own->at( "mp" ).get< int64_t >() >= 4 && distance <= 24.5;
    }
  }

  bool sprintReady( const Json& state )
  {
    const auto remaining = guardRemaining( state, "starting-action" );
    if( !idle( state ) )
      return false;
    if( state.at( "gm_rank" ) != 0 )
      throw ReadinessError( "Sprint readiness requires a non-GM player" );
    const auto* own = actor( state, state.at( "entity_id" ).get< uint32_t >() );
    if( !own )
      return false;
    if( own->at( "kind" ) != 1 || own->at( "hp" ).get< int64_t >() <= 0 )
      throw ReadinessError( "player was defeated while waiting for Sprint readiness" );
    return remaining == 0 && own->at( "tp" ).get< int64_t >() >= 50;
  }

  bool actionReady( const Json& state, uint32_t action, uint32_t target )
  {
    switch( action )
    {
      case 9: return startingMeleeReady( state, target, { 1, "Gladiator", 60, 1, -1 } );
      case 11: return savageBladeReady( state, target );
      case 53: return startingMeleeReady( state, target, { 2, "Pugilist", 60, 1, -1 } );
      case 54: return startingMeleeReady( state, target, { 2, "Pugilist", 50, 2, 0 } );
      case 142: return blizzardReady( state, target );
      default: throw ReadinessError( "action " + std::to_string( action ) + " has no readiness profile" );
    }
  }

  uint32_t damageValue( const Json& effect )
  {
    uint32_t total = 0;
    for( const auto& row : effect.at( "effects" ) )
      if( ( row.at( "type" ) == 3 || row.at( "type" ) == 5 ) && row.at( "flag" ) == 0 )
        total += row.at( "value" ).get< uint32_t >();
    return total;
  }

  bool committedDamage( const Json& state, const Json& effect, const Json& before )
  {
    const auto damage = damageValue( effect );
    if( damage == 0 )
      return false;
    const auto& effects = state.at( "combat" ).at( "effects" );
    if( std::find( effects.begin(), effects.end(), effect ) == effects.end() )
      return false;
    const auto hpBefore = before.at( "hp" ).get< int64_t >();
    for( const auto& row : state.at( "combat" ).at( "integrities" ) )
      if( row.at( "target" ) == effect.at( "target" ) && row.at( "result" ) == effect.at( "result" ) &&
          row.at( "hp_max" ) == before.at( "hp_max" ) &&
          row.at( "hp" ).get< int64_t >() == std::max< int64_t >( 0, hpBefore - damage ) )
        return true;
    return false;
  }
}
