// Natural level-four progression and the first Fast Blade -> Savage Blade combo.
// Four Gladiators defeat eighteen level-14 enemies (115 EXP each, relogging
// between kills so every cycle starts from persisted state) until they reach
// level 4 with 70 EXP; one of them then lands the combo while all five clients
// see both effects and their committed HP. No EXP, level or skill grants.
//
// Long: about 25 minutes against the running world.
#include "../../harness/Combat.h"
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"
#include <optional>
#include <set>

using namespace Sapphire::E2E;

class FastBladeCombo : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto combo = firstFastBladeCombo( data );
    expect( combo.at( "action" ) == 11 && combo.at( "level" ) == 4, "Savage Blade is the level-four Gladiator action" );
    expect( combo.at( "required_cumulative_exp" ) == 2000 && combo.at( "level_thresholds" ) == Json::array( { 300, 600, 1100 } ),
            "level four takes 2000 EXP over 300/600/1100: " + combo.dump() );
    expect( combo.at( "minimum_level_fourteen_defeats" ) == 18 && combo.at( "level_fourteen_enemy_exp" ) == 115,
            "eighteen level-14 defeats reach level four" );
    expect( combo.at( "level_one_enemy_exp" ) == 50 && combo.at( "minimum_level_one_defeats" ) == 40, "level-one enemies grant 50 EXP" );
    const uint32_t baseExp = enemyBaseExp( data, 14 );
    const size_t defeats = combo.at( "minimum_level_fourteen_defeats" ).get< size_t >();
    const auto thresholds = combo.at( "level_thresholds" ).get< std::vector< uint32_t > >();

    const auto pop = population( ctx, CentralThanalan::Territory );
    data.navi( CentralThanalan::Territory );
    // Eighteen defeats at a 60s respawn would take too long against one spawn, so
    // the fighters rotate across whichever level-14 enemy of this kind is healthy
    // nearby. They start beside this one.
    const auto spawns = pop.spawns( CentralThanalan::LevelFourteenEnemy, 14 );
    expect( spawns.size() >= 2, "several level-14 enemies of this kind spawn in Central Thanalan" );
    const auto spawn = pop.spawn( CentralThanalan::LevelFourteenSpawn );
    expect( spawn.baseId == CentralThanalan::LevelFourteenEnemy && spawn.level == 14 && !spawn.nonpop, "the starting spawn is the expected kind" );

    CharacterOptions options;
    options.territory = CentralThanalan::Territory;
    options.position = beside( spawn.position );
    std::vector< Fixture > fixtures;
    for( int index = 0; index < 4; ++index )
      fixtures.push_back( ctx.server().freshCharacter( options ) );
    const auto witnessFixture = ctx.server().freshCharacter( options );

    auto expectedProgress = [ & ]( uint32_t totalExp ) {
      uint32_t level = 1, remaining = totalExp;
      for( const auto threshold : thresholds )
      {
        if( remaining < threshold )
          break;
        remaining -= threshold;
        ++level;
      }
      return std::make_pair( level, remaining );
    };
    // The reward contract is written for "same level, +EXP"; a level-up moves the
    // EXP, so fold the received level/EXP back onto that shape once they match.
    auto normalize = [ & ]( const Bot::Rewards& after, const Bot::Rewards& before, uint32_t level, uint32_t exp ) -> std::optional< Bot::Rewards > {
      if( after.level != level || after.exp != exp )
        return std::nullopt;
      Bot::Rewards normalized = after;
      normalized.level = before.level;
      normalized.exp = before.exp + baseExp;
      return normalized;
    };

    auto login = [ & ]( const std::string& name, const Fixture& fixture ) -> Bot& {
      auto& bot = ctx.spawn( name );
      bot.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
      return bot;
    };
    auto allVisible = [ & ]( const std::vector< Bot* >& bots, const std::vector< uint32_t >& entities, const char* description ) {
      for( Bot* bot : bots )
        bot->waitState( [ & ]( const Json& s ) {
          for( const auto entity : entities )
            if( !Bot::actor( s, entity ) ) return false;
          return true;
        }, description, 30 );
    };

    std::optional< std::vector< Bot::Rewards > > expectedRewards;
    std::vector< Json > expectedInventories;
    for( size_t kill = 0; kill < defeats; ++kill )
    {
      const auto cycle = std::to_string( kill );
      std::vector< Bot* > fighters;
      for( size_t index = 0; index < fixtures.size(); ++index )
        fighters.push_back( &login( "combo-fighter-" + cycle + "-" + std::to_string( index ), fixtures[ index ] ) );
      Bot& witness = login( "combo-witness-" + cycle, witnessFixture );
      std::vector< Bot* > all = fighters;
      all.push_back( &witness );
      std::vector< uint32_t > entities;
      for( Bot* bot : all )
        entities.push_back( Bot::entity( bot->snapshot() ) );
      std::vector< Bot::Rewards > beforeRewards;
      for( size_t index = 0; index < fighters.size(); ++index )
      {
        const auto observed = waitRewardsObserved( *fighters[ index ], 1 );
        if( expectedRewards )
        {
          expect( Bot::rewardValues( observed, 1 ) == ( *expectedRewards )[ index ], fighters[ index ]->name() + ": rewards persisted across the relogin" );
          expect( observed.at( "rewards" ).at( "inventory" ) == expectedInventories[ index ], fighters[ index ]->name() + ": inventory persisted across the relogin" );
        }
        fighters[ index ]->waitState( [ & ]( const Json& s ) {
          const auto* own = Bot::actor( s, entities[ index ] );
          return own && own->at( "hp" ).get< int64_t >() > 0 && own->at( "hp" ) == own->at( "hp_max" );
        }, "natural pre-cycle HP restoration", 60 );
      }
      allVisible( all, entities, "all combo-progression clients visible" );
      const auto chosen = chooseAndApproach( all, witness, CentralThanalan::LevelFourteenEnemy, 14 );
      const uint32_t target = chosen.first;
      const Json targetBefore = chosen.second;
      expect( targetBefore.at( "hp" ) == targetBefore.at( "hp_max" ) && targetBefore.at( "hp" ) == 237, "the level-14 enemy starts at its 237 HP" );
      for( Bot* fighter : fighters )
        beforeRewards.push_back( Bot::rewardValues( fighter->snapshot(), 1 ) );
      const auto witnessBefore = Bot::rewardValues( waitRewardsObserved( witness, 1 ), 1 );

      const auto hits = defeatWithFastBlades( ctx, fighters, all, target, 237 );
      std::set< size_t > attackers;
      for( const auto& hit : hits )
        attackers.insert( hit.fighter );
      expect( attackers.size() == fighters.size(), "every fighter landed at least one hit" );

      const auto totalExp = baseExp * static_cast< uint32_t >( kill + 1 );
      const auto progress = expectedProgress( totalExp );
      const uint32_t level = progress.first, exp = progress.second;
      std::vector< Bot::Rewards > afterRewards;
      std::vector< Json > afterInventories;
      for( size_t index = 0; index < fighters.size(); ++index )
      {
        const auto& before = beforeRewards[ index ];
        const auto rewarded = fighters[ index ]->waitState( [ & ]( const Json& s ) {
          if( !s.at( "rewards" ).at( "inventory_ready" ).get< bool >() || s.at( "rewards" ).at( "exp_by_index" ).size() <= 1 )
            return false;
          const auto normalized = normalize( Bot::rewardValues( s, 1 ), before, level, exp );
          return normalized && combatRewardMatches( before, *normalized, baseExp );
        }, "exact level-four progression reward", 20 );
        const auto after = Bot::rewardValues( rewarded, 1 );
        combatRewardDelta( before, *normalize( after, before, level, exp ), baseExp );
        afterRewards.push_back( after );
        afterInventories.push_back( rewarded.at( "rewards" ).at( "inventory" ) );
      }
      expect( Bot::rewardValues( witness.snapshot(), 1 ) == witnessBefore, "the witness earned nothing" );
      for( Bot* bot : all )
        bot->waitState( [ & ]( const Json& s ) { return Bot::actor( s, target ) == nullptr; }, "progression target removed", 20 );
      ctx.log( "defeat " + std::to_string( kill + 1 ) + "/" + std::to_string( defeats ) + " (layout " + targetBefore.at( "layout_id" ).dump() +
               ", " + std::to_string( hits.size() ) + " hits): total EXP " + std::to_string( totalExp ) + " -> level " +
               std::to_string( level ) + ", " + std::to_string( exp ) + " EXP" );
      expectedRewards = afterRewards;
      expectedInventories = afterInventories;
      for( Bot* bot : all )
        bot->logout( 30, true );
    }

    // Everyone is level 4 with 70 EXP; one fighter lands the combo.
    std::vector< Bot* > fighters;
    for( size_t index = 0; index < fixtures.size(); ++index )
      fighters.push_back( &login( "combo-final-fighter-" + std::to_string( index ), fixtures[ index ] ) );
    Bot& witness = login( "combo-final-witness", witnessFixture );
    std::vector< Bot* > all = fighters;
    all.push_back( &witness );
    std::vector< uint32_t > entities;
    for( Bot* bot : all )
      entities.push_back( Bot::entity( bot->snapshot() ) );
    for( size_t index = 0; index < fighters.size(); ++index )
    {
      const auto observed = waitRewardsObserved( *fighters[ index ], 1 );
      expect( Bot::rewardValues( observed, 1 ) == ( *expectedRewards )[ index ], fighters[ index ]->name() + ": final rewards persisted" );
      expect( observed.at( "rewards" ).at( "inventory" ) == expectedInventories[ index ], fighters[ index ]->name() + ": final inventory persisted" );
      expect( observed.at( "rewards" ).at( "level_by_index" )[ 1 ] == 4 && observed.at( "rewards" ).at( "exp_by_index" )[ 1 ] == 70,
              fighters[ index ]->name() + " is level 4 with 70 EXP" );
    }
    allVisible( all, entities, "final combo clients visible" );
    const auto chosen = chooseAndApproach( all, witness, CentralThanalan::LevelFourteenEnemy, 14 );
    const uint32_t target = chosen.first;
    const Json finalTarget = chosen.second;
    Bot& actor = *fighters.front();
    const auto entity = entities.front();
    approachTarget( actor, target );
    auto ready = actor.waitActionReady( StarterAction::FastBlade, target, 45 );
    const Json beforeFast = *Bot::actor( ready, target );
    for( Bot* observer : all )
      observer->waitState( [ & ]( const Json& s ) {
        const auto* enemy = Bot::actor( s, target );
        return enemy && enemy->at( "hp" ) == beforeFast.at( "hp" );
      }, "final Fast Blade pre-state", 10 );
    const auto fastEffect = actor.action( StarterAction::FastBlade, target );
    expect( fastEffect.at( "source_effects" ) == Json::array( { Json{ { "type", 29 }, { "value", 9 }, { "flag", 0x80 }, { "args", { 0, 0, 0 } } } } ),
            "the final Fast Blade carries the combo marker: " + fastEffect.dump() );
    for( Bot* observer : all )
      observer->waitState( [ & ]( const Json& s ) { return committedDamage( s, fastEffect, beforeFast ); },
                           "final Fast Blade committed HP and combo readiness", 10 );

    const int64_t expectedSavageHp = std::max< int64_t >( 0, beforeFast.at( "hp" ).get< int64_t >() - damageValue( fastEffect ) );
    actor.waitState( [ & ]( const Json& s ) {
      const auto* enemy = Bot::actor( s, target );
      return enemy && enemy->at( "hp" ).get< int64_t >() == expectedSavageHp;
    }, "combo actor receives committed Fast Blade HP", 10 );
    ready = actor.waitActionReady( StarterAction::SavageBlade, target, 10 );
    const Json beforeSavage = *Bot::actor( ready, target );
    expect( beforeSavage.at( "hp" ).get< int64_t >() > 0 && Bot::actor( ready, entity )->at( "tp" ).get< int >() >= 60,
            "the target lives and the actor has the TP for Savage Blade" );
    for( Bot* observer : all )
    {
      const bool own = observer == &actor;
      observer->waitState( [ & ]( const Json& s ) {
        const auto* enemy = Bot::actor( s, target );
        const auto* self = Bot::actor( s, entity );
        if( !enemy || !self || enemy->at( "hp" ) != beforeSavage.at( "hp" ) )
          return false;
        const auto reference = own ? Bot::predicted( s ) : self->at( "position" ).get< Point >();
        return distance( enemy->at( "position" ).get< Point >(), reference ) < 3;
      }, "all clients see exact Savage Blade pre-state", 10 );
    }
    const auto savageEffect = actor.action( StarterAction::SavageBlade, target );
    expect( damageValue( savageEffect ) > 0, "Savage Blade deals damage" );
    expect( savageEffect.at( "source_effects" ) == Json::array( { Json{ { "type", 30 }, { "value", 0 }, { "flag", 0 }, { "args", { 0, 0, 0 } } },
                                                                   Json{ { "type", 29 }, { "value", 11 }, { "flag", 0x80 }, { "args", { 0, 0, 0 } } } } ),
            "Savage Blade reports the combo success and its own marker: " + savageEffect.dump() );
    for( Bot* observer : all )
      observer->waitState( [ & ]( const Json& s ) { return committedDamage( s, savageEffect, beforeSavage ); },
                           "identical combo-success effect and committed Savage Blade HP", 10 );
    const auto started = actor.waitState( [ & ]( const Json& s ) {
      for( const auto& row : s.at( "combat" ).at( "starts" ) )
        if( row.at( "source" ) == entity && row.at( "action" ) == 11 && row.at( "group" ) == 58 && row.at( "recast_centiseconds" ) == 250 )
          return true;
      return false;
    }, "received Savage Blade action start", 10 );
    ctx.log( "combo landed on " + std::to_string( target ) + " (layout " + finalTarget.at( "layout_id" ).dump() + "): Fast Blade " +
             std::to_string( damageValue( fastEffect ) ) + ", Savage Blade " + std::to_string( damageValue( savageEffect ) ) +
             "; persisted level " + started.at( "rewards" ).at( "level_by_index" )[ 1 ].dump() + ", EXP " +
             started.at( "rewards" ).at( "exp_by_index" )[ 1 ].dump() );
    // The combo target is left alive and damaged; it heals itself when it retreats.
    for( Bot* bot : all )
      bot->logout( 30 );
  }
};

EXPOSE_SCENARIO( FastBladeCombo );
