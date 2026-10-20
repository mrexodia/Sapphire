// Headless check of ToolkitPs3's actual Data::ExdData wrapper (no GL/MySQL).
#include "../ToolkitPs3/ExdData.h"
#include <iostream>

static void check( bool condition, const char* message )
{
  if( !condition ) throw std::runtime_error( message );
}

int main( int argc, char** argv )
{
  if( argc != 2 ) { std::cerr << "Usage: ps3_toolkit_data_smoke <monitor-sqpack-root>\n"; return 2; }
  try
  {
    Sapphire::Logger::init( "ps3-toolkit-data-smoke" );
    Data::ExdData data;
    check( data.init( argv[ 1 ] ), "Toolkit initialization" );
    check( data.getSheetNames().size() == 2131, "Expected monitor root sheet count" );
    auto territory = data.getRow< Excel::Ps3::TerritoryType >( 157 );
    check( territory && territory->getString( territory->data().Name ) == "s1d1", "Typed territory name" );
    check( territory->getString( territory->data().LVB ) == "ffxiv/sea_s1/dun/s1d1/level/s1d1", "Typed LVB reference" );
    check( territory->data().PCSearch && !territory->data().Stealth && !territory->data().Mount, "Territory boolean declaration order" );
    auto eobj = data.getRow< Excel::Ps3::EObj >( 2000405 );
    check( eobj && eobj->getString( eobj->data().Text.SGL ) == "unnatural ripples", "Typed EObj name" );
    check( eobj->data().EventHandler == 0xF0043 && eobj->data().SharedGroup == 0, "Typed EObj numerics" );
    check( eobj->data().Target && !eobj->data().DirectorControl && eobj->data().EyeCollision, "EObj packed bitfield order" );

    const auto& resident = data.getCategory( "Resident" ).get_data( xivps3::exd::Language::en );
    bool checkedSubrow = false;
    for( auto id : resident.get_ids() )
    {
      if( resident.get_subrow_count( id ) < 2 ) continue;
      auto fields0 = resident.get_row( id, 0 ), fields1 = resident.get_row( id, 1 );
      if( fields0 == fields1 ) continue;
      auto typed = data.getRow< Excel::Ps3::Resident >( id, 1 );
      check( typed && typed->data().Value == std::get< int32_t >( fields1[ 1 ] ) &&
             typed->data().Model == std::get< int32_t >( fields1[ 2 ] ) &&
             typed->data().Type == std::get< uint8_t >( fields1[ 0 ] ), "Toolkit forwards subrow ordinal" );
      checkedSubrow = true;
      break;
    }
    check( checkedSubrow, "Need a differing Resident subrow to prove forwarding" );
    const auto ids1 = data.getIdList< Excel::Ps3::EObj >();
    const auto ids2 = data.getIdList< Excel::Ps3::EObj >();
    check( ids1 == ids2 && !ids1.empty(), "Stable ID enumeration" );
    check( data.init( argv[ 1 ] ) && data.getRow< Excel::Ps3::EObj >( 2000405 )->data().Target,
           "Successful reload does not retain stale sheet copies" );
    std::cout << "Toolkit typed rows, packed flags, subrow forwarding, ID enumeration and reload passed\n";
    return 0;
  }
  catch( const std::exception& ex ) { std::cerr << ex.what() << '\n'; return 1; }
}
