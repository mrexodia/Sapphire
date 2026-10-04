// A fresh character logs in, keeps both connections alive for a while and logs out.
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"

using namespace Sapphire::E2E;

class LoginIdleLogout : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& bot = ctx.spawnCharacter( "login" );
    auto state = bot.snapshot();
    expect( state.at( "territory" ) != 0, "the world must place the character in a territory" );
    expect( Bot::actor( state, Bot::entity( state ) ) != nullptr, "the character must receive its own spawn" );
    const auto zone = state.at( "heartbeats" ).at( "zone" ).get< uint64_t >();
    const auto chat = state.at( "heartbeats" ).at( "chat" ).get< uint64_t >();
    bot.waitState( [ & ]( const Json& s ) {
      return s.at( "heartbeats" ).at( "zone" ).get< uint64_t >() >= zone + 2 &&
             s.at( "heartbeats" ).at( "chat" ).get< uint64_t >() >= chat + 2;
    }, "two rounds of keepalive replies on each channel", 15 );
    bot.logout();
  }
};

EXPOSE_SCENARIO( LoginIdleLogout );
