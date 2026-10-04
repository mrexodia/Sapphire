#pragma once
// Scenario registry and the few primitives a scenario body uses.
//
// A scenario is a class with a run() method, registered with EXPOSE_SCENARIO
// from a file under src/e2e/scenarios/<group>/<Name>.cpp. Its name is
// "<group>.<Name>". Failures are reported by throwing Failure, usually via
// expect(); anything else that throws (protocol errors, timeouts) fails the
// scenario too, with the bot journals printed for diagnosis.
#include <functional>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace Sapphire::E2E
{
  struct Failure : std::runtime_error { using std::runtime_error::runtime_error; };

  inline void expect( bool condition, const std::string& message )
  {
    if( !condition )
      throw Failure( message );
  }

  class Context;

  class Scenario
  {
  public:
    virtual ~Scenario() = default;
    virtual void run( Context& ctx ) = 0;
  };

  struct ScenarioInfo
  {
    std::string name;   // group.Name
    std::string group;
    std::string file;
    std::function< std::unique_ptr< Scenario >() > create;
  };

  class Registry
  {
  public:
    static Registry& instance();
    void add( ScenarioInfo info );
    const std::map< std::string, ScenarioInfo >& all() const { return m_scenarios; }
    const ScenarioInfo* find( const std::string& name ) const;
  private:
    std::map< std::string, ScenarioInfo > m_scenarios;
  };

  // "src/e2e/scenarios/<group>/<File>.cpp" -> "<group>.<File>"
  std::string scenarioNameFromFile( const std::string& file );

  template< class T >
  struct Registration
  {
    explicit Registration( const char* file )
    {
      const auto name = scenarioNameFromFile( file );
      Registry::instance().add( { name, name.substr( 0, name.find( '.' ) ), file,
                                  [] { return std::unique_ptr< Scenario >( new T() ); } } );
    }
  };
}

#define EXPOSE_SCENARIO( cls ) \
  static ::Sapphire::E2E::Registration< cls > cls##_scenario_registration( __FILE__ )
