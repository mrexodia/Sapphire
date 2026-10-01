#include "Manager/DevelopmentBotPlacement.h"
#include <iostream>
#include <limits>

using namespace Sapphire::World::Development;
using Json = nlohmann::json;

static void require( bool condition )
{
  if( !condition ) throw std::runtime_error( "development placement contract failed" );
}

int main()
{
  const Json source = {
    { "version", 2 }, { "purpose", "development-bot-placement" }, { "territory", 130 },
    { "approval_id", std::string( 32, 'a' ) }, { "provisioning_run_id", std::string( 32, 'c' ) },
    { "catalog_sha256", std::string( 64, 'b' ) },
    { "position", { 1.0, 2.0, 3.0 } },
    { "bots", { { { "entity_id", 10 }, { "character_id", 100 }, { "name", "Tester ABCDEFGHIJKL" } },
                { { "entity_id", 20 }, { "character_id", 200 }, { "name", "Tester MNOPQRSTUVWX" } } } }
  };
  const auto registry = parsePlacementRegistry( source );
  require( registry.bots[1].characterId == 200 && registry.position[2] == 3.f &&
           registry.provisioningRunId == std::string( 32, 'c' ) );
  auto rejects = []( const Json& value ) {
    bool rejected = false;
    try { parsePlacementRegistry( value ); } catch( const std::exception& ) { rejected = true; }
    require( rejected );
  };
  for( const auto& value : { Json( false ), Json( 1.5 ), Json( -1 ), Json( 0 ), Json( "10" ) } )
  {
    auto bad = source; bad["bots"][0]["entity_id"] = value; rejects( bad );
  }
  for( const auto& key : { "entity_id", "character_id", "name" } )
  {
    auto bad = source; bad["bots"][1][key] = bad["bots"][0][key]; rejects( bad );
  }
  auto bad = source; bad["territory"] = 182; rejects( bad );
  bad = source; bad["version"] = 1; rejects( bad );
  bad = source; bad["version"] = 2.0; rejects( bad );
  bad = source; bad["unexpected"] = true; rejects( bad );
  bad = source; bad["position"][0] = std::numeric_limits< double >::infinity(); rejects( bad );
  bad = source; bad["position"][0] = 1000; rejects( bad );
  bad = source; bad["position"][0] = "1"; rejects( bad );
  bad = source; bad["bots"][0]["name"] = "Human Viewer"; rejects( bad );
  bad = source; bad["bots"][0]["entity_id"] = uint64_t( UINT32_MAX ) + 1; rejects( bad );
  bad = source; bad["approval_id"] = "not-an-approval"; rejects( bad );
  bad = source; bad["provisioning_run_id"] = "not-a-provisioning-run"; rejects( bad );
  bad = source; bad.erase( "provisioning_run_id" ); rejects( bad );
  bad = source; bad["catalog_sha256"] = "no-catalog"; rejects( bad );
  const PlacementState idle{ 10, 100, "Tester ABCDEFGHIJKL", true, true, false, true, 0, 0, 182 };
  auto allowed = [&]( const PlacementState& state ) { return mayPlace( registry.bots[0], state, true, 1, 999, false ); };
  require( allowed( idle ) );
  require( !mayPlace( registry.bots[0], idle, false, 1, 999, false ) );
  require( !mayPlace( registry.bots[0], idle, true, 0, 999, false ) );
  require( !mayPlace( registry.bots[0], idle, true, 1, 100, false ) );
  require( !mayPlace( registry.bots[0], idle, true, 1, 999, true ) );
  for( int mutation = 0; mutation < 10; ++mutation )
  {
    auto state = idle;
    switch( mutation )
    {
      case 0: state.entityId = 11; break;
      case 1: state.characterId = 101; break;
      case 2: state.name = "Human Viewer"; break;
      case 3: state.sessionValid = false; break;
      case 4: state.loadingComplete = false; break;
      case 5: state.busy = true; break;
      case 6: state.alive = false; break;
      case 7: state.gmRank = 1; break;
      case 8: state.partyId = 1; break;
      case 9: state.territory = 141; break;
    }
    require( !allowed( state ) );
  }
  auto placed = idle; placed.territory = 130; require( allowed( placed ) );
  std::cout << "development bot placement contracts passed\n";
}
