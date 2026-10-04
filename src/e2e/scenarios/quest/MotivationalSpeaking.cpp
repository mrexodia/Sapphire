// Motivational Speaking (65686) through its real scene exchanges: cancelling the
// offer grants nothing, accepting and walking to the recipient while a second
// client watches, completing pays exactly the Quest row's exp and items, and
// the completion survives a fresh login. The quest data (NPC placements, route,
// rewards) is read from the game data at run time.
#include "QuestSteps.h"

using namespace Sapphire::E2E;
using namespace Sapphire::E2E::QuestSteps;

class MotivationalSpeaking : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto journey = questJourney( data, Uldah::MotivationalSpeaking, Uldah::Territory );
    ctx.log( "giver " + std::to_string( journey.giver.baseId ) + " at layout " + std::to_string( journey.giver.id ) + ", recipient " +
             std::to_string( journey.recipient.baseId ) + " at layout " + std::to_string( journey.recipient.id ) + ", route " +
             std::to_string( static_cast< int >( journey.routeLength ) ) + " m" );
    expect( journey.optionalItems.empty(), "optional reward selection is not part of this scenario" );
    expect( journey.classJob == 1, "a Gladiator quest" );
    // Independent authored expectation for this small known quest, not only the shared calculation.
    expect( journey.exp == 50 && journey.gil == 0, "Motivational Speaking pays 50 exp and no gil" );
    expect( journey.items.size() == 1 && journey.items[ 0 ].id == SpeakingScenes::Potion && journey.items[ 0 ].count == 2,
            "Motivational Speaking pays two potions" );

    CharacterOptions options;
    options.position = journey.route.front();
    auto& player = ctx.spawnCharacter( "quester", options );
    auto& observer = ctx.spawnCharacter( "quest-observer", options );
    const auto fixture = ctx.fixture( player );
    const auto actor = Bot::entity( player.snapshot() );
    const auto before = player.rewardSnapshot( journey.workIndex );
    expect( before.level == 1 && before.exp == 0, "a fresh character starts at level 1 without exp" );

    const auto expected = completeMotivationalSpeaking( ctx, player, &observer, journey, before, true );
    ctx.log( "completed; rewards " + describe( expected ) );

    player.logout();
    observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) == nullptr; }, "quester session cleanup", 30 );
    observer.logout();

    auto& reloaded = ctx.spawn( "quest-reloaded" );
    auto state = reloaded.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
    reloaded.expectQuestComplete( journey.quest );
    state = reloaded.expectRewards( expected, journey.workIndex );
    expect( !questActive( state, journey.quest ), "a completed quest is not active after a fresh login" );
    reloaded.logout();
  }
};

EXPOSE_SCENARIO( MotivationalSpeaking );
