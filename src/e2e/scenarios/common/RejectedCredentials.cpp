// The API refuses an unknown account and never hands out a session for it.
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"

using namespace Sapphire::E2E;

class RejectedCredentials : public Scenario
{
  void run( Context& ctx ) override
  {
    Json reply;
    const int status = ctx.server().tryLogin( "absent_e2e_user", "invalid", reply );
    expect( status == 400, "login with unknown credentials must be rejected with HTTP 400, got " + std::to_string( status ) );
    expect( !reply.contains( "sId" ), "a rejected login must not return a session id" );
  }
};

EXPOSE_SCENARIO( RejectedCredentials );
