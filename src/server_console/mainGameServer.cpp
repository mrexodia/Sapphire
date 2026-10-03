#include <chrono>
#include <iostream>
#include <thread>

#include "WorldServer.h"

#include <Util/CrashHandler.h>
#include <Service.h>

#include "Logging/Logger.h"
#include "Util/Util.h"

using namespace Sapphire;
using namespace Sapphire::World;

[[maybe_unused]]
Common::Util::CrashHandler crashHandler;

int main( int32_t argc, char* argv[] )
{
  Logger::init( "log/world" );

  auto pServer = std::make_shared< WorldServer >( "world.ini" );

  Common::Service< WorldServer >::set( pServer );

  pServer->init( argc, argv );
  if( !pServer->isRunning() )
    return 1;

  while( pServer->isRunning() )
  {
    auto tickCount = Common::Util::getTimeMs();
    pServer->update( tickCount );

    // Leave bounded CPU time for the network and database workers. Without a
    // pause this loop busy-spins, which can starve encrypted session delivery
    // on single-core and quota-constrained hosts without advancing millisecond
    // based world state any faster.
    std::this_thread::sleep_for( std::chrono::milliseconds( 1 ) );
  }

  pServer->shutdown();
  return 0;
}
