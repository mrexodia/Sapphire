#include "Scenario.h"
#include <algorithm>

namespace Sapphire::E2E
{
  Registry& Registry::instance()
  {
    static Registry registry;
    return registry;
  }

  void Registry::add( ScenarioInfo info )
  {
    if( m_scenarios.count( info.name ) )
      throw std::logic_error( "duplicate scenario name " + info.name );
    m_scenarios[ info.name ] = std::move( info );
  }

  const ScenarioInfo* Registry::find( const std::string& name ) const
  {
    auto it = m_scenarios.find( name );
    return it == m_scenarios.end() ? nullptr : &it->second;
  }

  std::string scenarioNameFromFile( const std::string& file )
  {
    std::string path = file;
    std::replace( path.begin(), path.end(), '\\', '/' );
    const auto dot = path.rfind( '.' );
    if( dot != std::string::npos )
      path.resize( dot );
    const auto slash = path.rfind( '/' );
    const std::string name = slash == std::string::npos ? path : path.substr( slash + 1 );
    std::string group = "misc";
    if( slash != std::string::npos )
    {
      const auto previous = path.rfind( '/', slash - 1 );
      group = path.substr( previous == std::string::npos ? 0 : previous + 1, slash - ( previous == std::string::npos ? 0 : previous + 1 ) );
    }
    return group + "." + name;
  }
}
