#include "ExdData.h"

bool Data::ExdData::init( const std::string& path )
{
  try
  {
    auto data = std::make_shared< xivps3::dat::GameData >( path );
    auto sheets = std::make_shared< xivps3::exd::ExdData >( *data );
    // Keep the old catalog alive until its GameData reference can be released.
    m_exd_data = std::move( sheets );
    m_data = std::move( data );
    return true;
  }
  catch( const std::exception& ex )
  {
    Sapphire::Logger::error( "Cannot load PS3 data from {}: {}", path, ex.what() );
    return false;
  }
}
