#include "Combat.h"
#include "Scenario.h"
#include <algorithm>
#include <fstream>
#include <limits>
#include <set>

namespace Sapphire::E2E
{
  // -- population -------------------------------------------------------------

  Population::Population( const std::filesystem::path& serverDir, const std::string& zone ) :
    m_file( serverDir / "data" / "bnpcs" / zone / ( zone + ".json" ) )
  {
    std::ifstream input( m_file );
    if( !input )
      throw std::runtime_error( "cannot read the world's population file " + m_file.string() );
    Json population;
    input >> population;
    for( const auto& [ groupName, group ] : population.items() )
    {
      if( !group.is_object() || !group.contains( "bnpcs" ) )
        continue;
      for( const auto& [ layoutId, row ] : group.at( "bnpcs" ).items() )
      {
        const auto& base = row.at( "baseInfo" );
        const auto& pop = row.at( "popInfo" );
        Spawn spawn;
        spawn.group = groupName;
        spawn.layoutId = static_cast< uint32_t >( std::stoul( layoutId ) );
        spawn.baseId = base.at( "baseId" ).get< uint32_t >();
        spawn.level = base.at( "level" ).get< uint8_t >();
        spawn.activeType = base.at( "activeType" ).get< int >();
        spawn.position = base.at( "position" ).get< Point >();
        spawn.rotation = base.at( "rotation" ).get< float >();
        spawn.popInterval = pop.at( "popInterval" ).get< int >();
        spawn.nonpop = pop.at( "nonpop" ).get< int >() != 0;
        spawn.invalidRepop = pop.at( "invalidRepop" ).get< int >() != 0;
        if( row.contains( "SenseInfo" ) )
        {
          spawn.sense = row.at( "SenseInfo" ).at( "Sense" ).get< std::array< int, 2 > >();
          spawn.senseRange = row.at( "SenseInfo" ).at( "SenseRange" ).get< std::array< int, 2 > >();
        }
        if( row.contains( "Behaviour" ) )
          spawn.wanderingRange = row.at( "Behaviour" ).at( "wanderingRange" ).get< int >();
        m_spawns.emplace( spawn.layoutId, spawn );
      }
    }
  }

  Spawn Population::spawn( uint32_t layoutId ) const
  {
    if( m_spawns.count( layoutId ) != 1 )
      throw std::runtime_error( "spawn " + std::to_string( layoutId ) + " occurs " + std::to_string( m_spawns.count( layoutId ) ) +
                                " times in " + m_file.string() );
    return m_spawns.find( layoutId )->second;
  }

  std::vector< Spawn > Population::spawns( uint32_t baseId, uint8_t level ) const
  {
    std::vector< Spawn > rows;
    for( const auto& [ id, spawn ] : m_spawns )
      if( spawn.baseId == baseId && spawn.level == level && !spawn.nonpop )
        rows.push_back( spawn );
    return rows;
  }

  Population population( Context& ctx, uint16_t territory )
  {
    return Population( ctx.config().serverDir, ctx.data().internalName( territory ) );
  }

  // -- action metadata --------------------------------------------------------

  Json actionMeta( GameData& data, uint32_t actionId )
  {
    auto row = data.row< Excel::Action >( actionId );
    if( !row )
      throw std::runtime_error( "action " + std::to_string( actionId ) + " has no Action row" );
    const auto& action = row->data();
    auto growth = data.row< Excel::ParamGrow >( action.Level );
    auto classJob = data.row< Excel::ClassJob >( action.UseClassJob );
    if( !growth || !classJob )
      throw std::runtime_error( "action " + std::to_string( actionId ) + " has no class/level data" );
    return { { "action", actionId }, { "class_job", action.UseClassJob }, { "work_index", classJob->data().WorkIndex },
             { "level", action.Level }, { "base_exp", growth->data().BaseExp }, { "category", action.Category },
             { "cost_type", action.CostType }, { "cost", action.CostValue }, { "range", action.SelectRange },
             { "cast_ms", action.CastTime * 100 }, { "recast_ms", action.RecastTime * 100 },
             { "recast_group", action.RecastGroup }, { "effect_type", action.EffectType },
             { "target_enemy", action.SelectEnemy != 0 } };
  }

  uint32_t enemyBaseExp( GameData& data, uint8_t level )
  {
    auto growth = data.row< Excel::ParamGrow >( level );
    if( !growth || !growth->data().BaseExp )
      throw std::runtime_error( "level " + std::to_string( level ) + " has no enemy EXP metadata" );
    return growth->data().BaseExp;
  }

  Json firstFastBladeCombo( GameData& data )
  {
    auto combo = actionMeta( data, 11 );
    uint32_t required = 0;
    Json thresholds = Json::array();
    for( uint32_t level = 1; level < combo.at( "level" ).get< uint32_t >(); ++level )
    {
      auto growth = data.row< Excel::ParamGrow >( level );
      if( !growth || !growth->data().NextExp )
        throw std::runtime_error( "level " + std::to_string( level ) + " has no EXP threshold" );
      required += growth->data().NextExp;
      thresholds.push_back( growth->data().NextExp );
    }
    const auto levelOne = enemyBaseExp( data, 1 );
    const auto levelFourteen = enemyBaseExp( data, 14 );
    combo[ "required_cumulative_exp" ] = required;
    combo[ "level_thresholds" ] = thresholds;
    combo[ "level_one_enemy_exp" ] = levelOne;
    combo[ "minimum_level_one_defeats" ] = ( required + levelOne - 1 ) / levelOne;
    combo[ "level_fourteen_enemy_exp" ] = levelFourteen;
    combo[ "minimum_level_fourteen_defeats" ] = ( required + levelFourteen - 1 ) / levelFourteen;
    return combo;
  }

  // -- homepoint --------------------------------------------------------------

  // -- routes -----------------------------------------------------------------

  Route boundedRoute( GameData& data, uint16_t territory, const Point& start, const Point& origin, float requested,
                      float minimumDisplacement, float maximumLength )
  {
    Route best;
    best.length = std::numeric_limits< double >::infinity();
    for( const auto& delta : std::array< Point, 4 >{ { { requested, 0, 0 }, { -requested, 0, 0 }, { 0, 0, requested }, { 0, 0, -requested } } } )
    {
      Point end = start;
      for( size_t axis = 0; axis < 3; ++axis )
        end[ axis ] += delta[ axis ];
      try
      {
        auto points = data.route( territory, start, end );
        const auto length = data.routeLength( points );
        if( horizontal( points.back(), origin ) >= minimumDisplacement && length <= maximumLength && length < best.length )
          best = { std::move( points ), length };
      }
      catch( const std::exception& )
      {
        // No complete corridor that way; never use a partial route.
      }
    }
    if( best.points.empty() )
      throw std::runtime_error( "no complete route of at most " + std::to_string( static_cast< int >( maximumLength ) ) +
                                "m displacing " + std::to_string( static_cast< int >( minimumDisplacement ) ) + "m" );
    return best;
  }

  ProximityApproach proximityApproach( GameData& data, uint16_t territory, const Spawn& enemy )
  {
    constexpr double pi = 3.14159265358979323846;
    auto radial = [ & ]( double angle, double metres ) {
      Point point = enemy.position;
      point[ 0 ] += static_cast< float >( std::sin( angle ) * metres );
      point[ 2 ] += static_cast< float >( std::cos( angle ) * metres );
      return point;
    };
    ProximityApproach approach;
    // Start 20m out, well beyond the 14m sense range, then arc around the enemy
    // at 3m so it sees the player without the player ever acting.
    Point previous = radial( enemy.rotation, 20.0 );
    for( size_t index = 0; index < 9; ++index )
    {
      const auto next = radial( enemy.rotation + static_cast< double >( index ) * pi / 4.0, 3.0 );
      auto segment = data.route( territory, previous, next );
      if( !approach.route.points.empty() && !segment.empty() )
        segment.erase( segment.begin() );
      approach.route.points.insert( approach.route.points.end(), segment.begin(), segment.end() );
      previous = next;
    }
    approach.route.length = data.routeLength( approach.route.points );
    const auto startDistance = horizontal( approach.route.points.front(), enemy.position );
    double closest = std::numeric_limits< double >::infinity();
    for( const auto& point : approach.route.points )
      closest = std::min( closest, horizontal( point, enemy.position ) );
    if( approach.route.points.empty() || approach.route.length < 20 || approach.route.length > 80 || startDistance < 15 ||
        startDistance > 25 || closest > 5 )
      throw std::runtime_error( "no complete bounded active-vision approach route" );
    bool haveWitness = false;
    for( size_t index = 0; index < 16 && !haveWitness; ++index )
    {
      try
      {
        const auto angle = enemy.rotation + static_cast< double >( index ) * pi / 8.0;
        const auto candidate = data.route( territory, enemy.position, radial( angle, 30.0 ) ).back();
        const auto witnessDistance = horizontal( candidate, enemy.position );
        if( witnessDistance >= 25 && witnessDistance <= 35 && horizontal( candidate, approach.route.points.front() ) >= 5 )
        {
          approach.witness = candidate;
          haveWitness = true;
        }
      }
      catch( const std::exception& )
      {
        // Unreachable direction; try the next one.
      }
    }
    if( !haveWitness )
      throw std::runtime_error( "no bounded active-vision witness position" );
    return approach;
  }

  // -- choosing natural targets ------------------------------------------------

  std::vector< Enemy > healthyEnemies( const Json& state, uint32_t baseId, uint8_t level, double maximum,
                                       std::optional< Point > origin, double isolation )
  {
    const Point centre = origin ? *origin : Bot::predicted( state );
    std::vector< Point > hostiles;
    for( const auto& [ key, actor ] : state.at( "actors" ).items() )
      if( actor.at( "kind" ) == 2 && actor.at( "hp" ).get< int64_t >() > 0 )
        hostiles.push_back( actor.at( "position" ).get< Point >() );
    std::vector< Enemy > rows;
    for( const auto& [ key, actor ] : state.at( "actors" ).items() )
    {
      if( actor.at( "kind" ) != 2 || actor.at( "base_id" ) != baseId || actor.at( "level" ) != level )
        continue;
      const auto hp = actor.at( "hp" ).get< int64_t >();
      if( hp <= 0 || hp != actor.at( "hp_max" ).get< int64_t >() )
        continue;
      const auto position = actor.at( "position" ).get< Point >();
      if( distance( position, centre ) > maximum )
        continue;
      if( isolation > 0 )
      {
        // The enemy itself is among the hostiles, so "alone" means exactly one.
        const auto neighbours = std::count_if( hostiles.begin(), hostiles.end(), [ & ]( const Point& p ) {
          return distance( p, position ) < isolation;
        } );
        if( neighbours > 1 )
          continue;
      }
      rows.emplace_back( static_cast< uint32_t >( std::stoul( key ) ), actor );
    }
    std::stable_sort( rows.begin(), rows.end(), [ & ]( const Enemy& a, const Enemy& b ) {
      return distance( a.second.at( "position" ).get< Point >(), centre ) < distance( b.second.at( "position" ).get< Point >(), centre );
    } );
    return rows;
  }

  Enemy waitHealthyEnemy( Bot& bot, uint32_t baseId, uint8_t level, double maximum, double timeout, double isolation )
  {
    std::string description = "healthy level-" + std::to_string( level ) + " enemy " + std::to_string( baseId ) + " within " +
                              std::to_string( static_cast< int >( maximum ) ) + "m";
    if( isolation > 0 )
      description += ", none other within " + std::to_string( static_cast< int >( isolation ) ) + "m";
    auto state = bot.waitState( [ & ]( const Json& s ) {
      return !healthyEnemies( s, baseId, level, maximum, std::nullopt, isolation ).empty();
    }, description, timeout );
    return healthyEnemies( state, baseId, level, maximum, std::nullopt, isolation ).front();
  }

  Json approachTarget( Bot& bot, uint32_t target, double within, int attempts, float speed )
  {
    for( int attempt = 0; attempt < attempts; ++attempt )
    {
      auto state = bot.snapshot();
      const auto* actor = Bot::actor( state, target );
      if( !actor || actor->at( "hp" ).get< int64_t >() <= 0 )
        throw Failure( bot.name() + ": target " + std::to_string( target ) + " disappeared during the approach" );
      const auto position = actor->at( "position" ).get< Point >();
      if( distance( position, Bot::predicted( state ) ) < within )
        return state;
      bot.walkTo( beside( position ), speed, 30 );
    }
    throw Failure( bot.name() + ": could not reach target " + std::to_string( target ) + " in " + std::to_string( attempts ) + " legs" );
  }

  Enemy chooseAndApproach( const std::vector< Bot* >& bots, Bot& witness, uint32_t baseId, uint8_t level )
  {
    // Another scenario may have just killed the enemy beside the spawn point and
    // level-14 enemies take 60s to respawn, so allow two respawn cycles.
    const auto chosen = waitHealthyEnemy( witness, baseId, level, 60.0, 120, 12.0 );
    const auto target = chosen.first;
    for( Bot* bot : bots )
      approachTarget( *bot, target );
    for( Bot* bot : bots )
      bot->waitState( [ & ]( const Json& s ) {
        const auto* enemy = Bot::actor( s, target );
        return enemy && enemy->at( "hp" ).get< int64_t >() > 0 && enemy->at( "hp" ) == enemy->at( "hp_max" );
      }, "every client sees the chosen healthy target", 10 );
    return { target, *Bot::actor( witness.snapshot(), target ) };
  }

  std::vector< Hit > defeatWithFastBlades( Context& ctx, const std::vector< Bot* >& fighters, const std::vector< Bot* >& observers,
                                           uint32_t target, int64_t startingHp, size_t maximumHits )
  {
    const Json comboMarker = Json::array( { Json{ { "type", 29 }, { "value", 9 }, { "flag", 0x80 }, { "args", { 0, 0, 0 } } } } );
    std::vector< uint32_t > entities;
    for( Bot* fighter : fighters )
      entities.push_back( Bot::entity( fighter->snapshot() ) );
    std::vector< Hit > hits;
    int64_t expectedHp = startingHp;
    while( expectedHp > 0 )
    {
      expect( hits.size() < maximumHits, "bounded multi-attacker sequence did not defeat the target" );
      for( size_t index = 0; index < fighters.size() && expectedHp > 0; ++index )
      {
        Bot& fighter = *fighters[ index ];
        const auto entity = entities[ index ];
        fighter.waitState( [ & ]( const Json& s ) {
          const auto* enemy = Bot::actor( s, target );
          return enemy && enemy->at( "hp" ).get< int64_t >() == expectedHp;
        }, "acting fighter receives exact committed high-level HP", 10 );
        // Enemies roam while idle; close the gap again before each hit.
        approachTarget( fighter, target );
        const auto ready = fighter.waitActionReady( StarterAction::FastBlade, target, 45 );
        const Json before = *Bot::actor( ready, target );
        expect( before.at( "hp" ).get< int64_t >() == expectedHp && expectedHp > 0, "the acting fighter sees the exact pre-hit HP" );
        for( Bot* observer : observers )
        {
          const bool own = observer == &fighter;
          observer->waitState( [ & ]( const Json& s ) {
            const auto* enemy = Bot::actor( s, target );
            const auto* self = Bot::actor( s, entity );
            if( !enemy || !self || enemy->at( "hp" ).get< int64_t >() != expectedHp || self->at( "hp" ).get< int64_t >() <= 0 )
              return false;
            const auto reference = own ? Bot::predicted( s ) : self->at( "position" ).get< Point >();
            return distance( enemy->at( "position" ).get< Point >(), reference ) < 3;
          }, "all clients see exact pre-hit HP and acting fighter in range", 10 );
        }
        const auto effect = fighter.action( StarterAction::FastBlade, target );
        expect( effect.at( "source" ) == entity && effect.at( "action" ) == 9 && damageValue( effect ) > 0,
                fighter.name() + ": Fast Blade is its own damaging effect" );
        expect( effect.at( "source_effects" ) == comboMarker, fighter.name() + ": Fast Blade carries the combo marker: " + effect.dump() );
        for( Bot* observer : observers )
          observer->waitState( [ & ]( const Json& s ) { return committedDamage( s, effect, before ); },
                               "all clients receive identical high-level damage and committed HP", 10 );
        Hit hit;
        hit.fighter = index;
        hit.effect = effect;
        hit.beforeHp = before.at( "hp" ).get< int64_t >();
        hit.afterHp = std::max< int64_t >( 0, hit.beforeHp - damageValue( effect ) );
        hits.push_back( hit );
        expectedHp = hit.afterHp;
        ctx.log( fighter.name() + " hit for " + std::to_string( damageValue( effect ) ) + ", target HP " + std::to_string( hit.beforeHp ) +
                 " -> " + std::to_string( hit.afterHp ) );
      }
    }
    return hits;
  }

  // -- rewards ----------------------------------------------------------------

  Json waitRewardsObserved( Bot& bot, size_t workIndex, double timeout )
  {
    return bot.waitState( [ & ]( const Json& s ) {
      return s.at( "rewards" ).at( "inventory_ready" ).get< bool >() && s.at( "rewards" ).at( "exp_by_index" ).size() > workIndex;
    }, "inventory and experience observed", timeout );
  }

  std::map< uint32_t, int64_t > combatRewardDelta( const Bot::Rewards& before, const Bot::Rewards& after, uint32_t baseExp )
  {
    if( baseExp == 0 )
      throw Failure( "combat base EXP must be positive" );
    if( after.exp != before.exp + baseExp || after.level != before.level )
      throw Failure( "combat EXP/level reward mismatch" );
    if( after.currencies != before.currencies )
      throw Failure( "combat unexpectedly changed currency" );
    std::map< uint32_t, int64_t > delta;
    for( const auto& [ item, count ] : before.items )
      delta[ item ] -= count;
    for( const auto& [ item, count ] : after.items )
      delta[ item ] += count;
    for( auto it = delta.begin(); it != delta.end(); )
    {
      if( it->second < 0 )
        throw Failure( "combat loot removed an existing item" );
      it = it->second == 0 ? delta.erase( it ) : std::next( it );
    }
    std::vector< uint32_t > firstPool;
    for( const uint32_t item : { 8u, 9u } )
      if( delta.count( item ) && delta.at( item ) == 5 )
        firstPool.push_back( item );
    const auto variable = delta.count( 4551 ) ? delta.at( 4551 ) : 0;
    const std::map< uint32_t, int64_t > expected{ { firstPool.empty() ? 0u : firstPool.front(), 5 }, { 5016, 1 }, { 12728, 1 }, { 4551, variable } };
    if( firstPool.size() != 1 || !variable || delta != expected )
      throw Failure( "combat loot does not match enabled testTable pools" );
    if( variable < 1 || variable > 3 )
      throw Failure( "combat variable-quantity loot is out of range" );
    return delta;
  }

  bool combatRewardMatches( const Bot::Rewards& before, const Bot::Rewards& after, uint32_t baseExp )
  {
    try
    {
      combatRewardDelta( before, after, baseExp );
      return true;
    }
    catch( const Failure& )
    {
      return false;
    }
  }

  void requireUnchangedDeathState( const Bot::Rewards& beforeRewards, const Json& beforeInventory,
                                   const Bot::Rewards& afterRewards, const Json& afterInventory )
  {
    if( !beforeInventory.is_object() || !afterInventory.is_object() )
      throw Failure( "death inventory state must be received mappings" );
    if( beforeRewards != afterRewards )
      throw Failure( "death changed received EXP, level, currency or item totals" );
    if( beforeInventory != afterInventory )
      throw Failure( "death changed received inventory rows" );
  }
}
