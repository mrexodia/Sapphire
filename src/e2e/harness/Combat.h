#pragma once
// What the combat scenarios share: the world's own BNpc population records,
// action metadata from the Excel sheets, the homepoint a defeated player
// returns to, routes on the zone navmesh, and the rules for picking natural
// targets on a shared long-running world.
//
// Enemies respawn on their own after their popInterval and heal fully when
// they retreat to spawn, so scenarios wait for a healthy enemy instead of
// resetting the world. Roaming enemies cluster; fights against level-14
// enemies pick a target with no other living hostile nearby.
#include "Context.h"
#include "GameData.h"
#include "Transitions.h"   // homepoint(): where a Return lands
#include <cmath>
#include <filesystem>
#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace Sapphire::E2E
{
  inline double distance( const Point& a, const Point& b )
  {
    return std::sqrt( std::pow( a[ 0 ] - b[ 0 ], 2 ) + std::pow( a[ 1 ] - b[ 1 ], 2 ) + std::pow( a[ 2 ] - b[ 2 ], 2 ) );
  }
  inline double horizontal( const Point& a, const Point& b )
  {
    return std::hypot( a[ 0 ] - b[ 0 ], a[ 2 ] - b[ 2 ] );
  }
  // One metre beside a spawn: face() has no direction for coincident actors.
  inline Point beside( Point position )
  {
    position[ 0 ] += 1.0f;
    return position;
  }

  // -- population -------------------------------------------------------------
  // One BNpc spawn record as the world loads it from data/bnpcs/<zone>/<zone>.json.
  struct Spawn
  {
    std::string group;
    uint32_t layoutId = 0;
    uint32_t baseId = 0;
    uint8_t level = 0;
    int activeType = 0;
    Point position{};
    float rotation = 0;
    int popInterval = 0;         // seconds from defeat to respawn
    bool nonpop = false;
    bool invalidRepop = false;
    std::array< int, 2 > sense{};
    std::array< int, 2 > senseRange{};
    int wanderingRange = 0;
  };

  class Population
  {
  public:
    // Reads <serverDir>/data/bnpcs/<zone>/<zone>.json, the file the world itself loads.
    Population( const std::filesystem::path& serverDir, const std::string& zone );
    // The record with this layout id; throws unless exactly one group has it.
    Spawn spawn( uint32_t layoutId ) const;
    // Every ordinary (nonpop 0) spawn of one kind and level.
    std::vector< Spawn > spawns( uint32_t baseId, uint8_t level ) const;
    const std::filesystem::path& file() const { return m_file; }

  private:
    std::filesystem::path m_file;
    std::multimap< uint32_t, Spawn > m_spawns;
  };
  // The population of a territory, named through its TerritoryType row ("w1f2").
  Population population( Context& ctx, uint16_t territory );

  // -- action metadata --------------------------------------------------------
  // Excel::Action joined with ParamGrow and ClassJob, as the scenarios' profile
  // of a starting action: action, class_job, work_index, level, base_exp,
  // category, cost_type, cost, range, cast_ms, recast_ms, recast_group,
  // effect_type, target_enemy.
  Json actionMeta( GameData& data, uint32_t actionId );
  // Savage Blade's metadata plus what reaching its level takes: the ParamGrow
  // thresholds below it, their sum, and how many level-1 / level-14 defeats cover it.
  Json firstFastBladeCombo( GameData& data );
  // The fixed EXP a defeated enemy of this level grants (ParamGrow BaseExp).
  uint32_t enemyBaseExp( GameData& data, uint8_t level );


  // -- routes -----------------------------------------------------------------
  struct Route
  {
    std::vector< Point > points;
    double length = 0;
  };
  // The shortest complete route from `start` that ends at least
  // `minimumDisplacement` (horizontal) from `origin`, trying `requested` metres
  // along each axis; never longer than `maximumLength`.
  Route boundedRoute( GameData& data, uint16_t territory, const Point& start, const Point& origin, float requested,
                      float minimumDisplacement, float maximumLength );
  struct ProximityApproach
  {
    Route route;        // from 20m in front of the enemy, arcing around it at 3m
    Point witness{};    // 25..35m out, at least 5m from the route start
  };
  // A walk from outside an active-vision enemy's sense range into it.
  ProximityApproach proximityApproach( GameData& data, uint16_t territory, const Spawn& enemy );

  // -- choosing natural targets ------------------------------------------------
  using Enemy = std::pair< uint32_t, Json >;   // entity id, actor row
  // Full-HP enemies of one kind within `maximum` of `origin` (default: the
  // bot's predicted position), nearest first. With `isolation` set, only enemies
  // with no other living hostile within that many metres qualify.
  std::vector< Enemy > healthyEnemies( const Json& state, uint32_t baseId, uint8_t level, double maximum = 60.0,
                                       std::optional< Point > origin = std::nullopt, double isolation = 0.0 );
  // Wait for a healthy enemy of one kind to be visible (covers one respawn).
  Enemy waitHealthyEnemy( Bot& bot, uint32_t baseId, uint8_t level, double maximum = 60.0, double timeout = 90,
                          double isolation = 0.0 );
  // Walk toward a (possibly roaming) enemy using only received positions.
  Json approachTarget( Bot& bot, uint32_t target, double within = 2.5, int attempts = 6, float speed = 6.0f );
  // The witness picks the nearest healthy isolated enemy of one kind; every bot
  // walks beside it and confirms the same healthy target before the first hit.
  Enemy chooseAndApproach( const std::vector< Bot* >& bots, Bot& witness, uint32_t baseId, uint8_t level );

  // -- group fights -----------------------------------------------------------
  struct Hit
  {
    size_t fighter = 0;     // index into the fighters
    Json effect;
    int64_t beforeHp = 0;
    int64_t afterHp = 0;
  };
  // Fighters take turns landing Fast Blades on `target` until it is defeated.
  // Before each hit every observer sees the exact pre-hit HP and the acting
  // fighter in melee range (the fighter judges its own range from its predicted
  // position: the server does not echo a player's own movement); afterwards every
  // observer sees the identical effect and the committed HP.
  std::vector< Hit > defeatWithFastBlades( Context& ctx, const std::vector< Bot* >& fighters, const std::vector< Bot* >& observers,
                                           uint32_t target, int64_t startingHp, size_t maximumHits = 40 );

  // -- rewards ----------------------------------------------------------------
  // The state once inventory and the class's EXP row have been received.
  Json waitRewardsObserved( Bot& bot, size_t workIndex, double timeout = 10 );
  // The server's current fixed BNpc EXP and testTable loot contract: +baseExp,
  // same level, no currency change, 5 of item 8 xor 9, one 5016, one 12728,
  // one to three 4551 and nothing removed.
  bool combatRewardMatches( const Bot::Rewards& before, const Bot::Rewards& after, uint32_t baseExp );
  // The same check, throwing Failure with the reason; returns the item delta.
  std::map< uint32_t, int64_t > combatRewardDelta( const Bot::Rewards& before, const Bot::Rewards& after, uint32_t baseExp );
  // Exact equality of tracked rewards and complete inventory rows across a
  // defeat or return; durability and other penalties are not exposed.
  void requireUnchangedDeathState( const Bot::Rewards& beforeRewards, const Json& beforeInventory,
                                   const Bot::Rewards& afterRewards, const Json& afterInventory );
}
