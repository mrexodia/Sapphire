// Compile the real application binder against a non-owning connector double.
// SQL/driver behavior is separately exercised by live persistence scenarios.
#include "PreparedStatement.h"
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <iterator>
#include <new>
#include <stdexcept>

namespace { std::atomic< long long > liveAllocations{ 0 }; }
// Count balanced application C++ allocations; warm up standard-library caches
// before measuring. This detects lost streams without an RSS/allocator heuristic.
void* operator new( std::size_t size )
{
  auto p = std::malloc( size ? size : 1 );
  if( !p ) throw std::bad_alloc();
  ++liveAllocations;
  return p;
}
void operator delete( void* p ) noexcept
{
  if( p ) { --liveAllocations; std::free( p ); }
}
void* operator new[]( std::size_t size ) { return ::operator new( size ); }
void operator delete[]( void* p ) noexcept { ::operator delete( p ); }
void operator delete( void* p, std::size_t ) noexcept { ::operator delete( p ); }
void operator delete[]( void* p, std::size_t ) noexcept { ::operator delete( p ); }

#define CHECK(x) do { if( !(x) ) throw std::runtime_error( #x ); } while( false )

static std::string readBlob( Mysql::PreparedStatement& driver, uint32_t index )
{
  auto stream = driver.blobs.at( index );
  CHECK( stream );
  return { std::istreambuf_iterator< char >( *stream ), std::istreambuf_iterator< char >() };
}

static void exercise()
{
  auto driver = std::make_shared< Mysql::PreparedStatement >();
  Sapphire::Db::PreparedStatement statement( 1 );
  statement.setMysqlPS( driver );
  const std::vector< uint8_t > bytes{ 0, 1, 255, 0, 127 };
  statement.setBinary( 1, bytes );
  statement.setBinary( 2, {} );
  statement.bindParameters();
  CHECK( readBlob( *driver, 1 ) == std::string( reinterpret_cast< const char* >( bytes.data() ), bytes.size() ) );
  CHECK( readBlob( *driver, 2 ).empty() );
  // Reading occurs after bindParameters returns: streams must outlive binding.
  for( int i = 0; i < 32; ++i )
  {
    statement.setBinary( 1, std::vector< uint8_t >( 4096, static_cast< uint8_t >( i ) ) );
    statement.bindParameters();
    CHECK( readBlob( *driver, 1 ) == std::string( 4096, static_cast< char >( i ) ) );
    CHECK( readBlob( *driver, 2 ).empty() );
  }
  statement.setNull( 1 );
  statement.bindParameters();
  CHECK( driver->blobs.count( 1 ) == 0 );
  CHECK( readBlob( *driver, 2 ).empty() );
  statement.setBinary( 1, bytes );
  driver->throwOn = 2;
  bool threw = false;
  try { statement.bindParameters(); }
  catch( const std::runtime_error& ) { threw = true; }
  CHECK( threw );
  // A failed partial bind must also release every owned stream, on rebind or
  // destruction. Do not execute a failed binding through dangling driver slots.
}

int main()
{
  try
  {
    exercise(); // Lazy standard-library initialization is outside the measurement.
    auto before = liveAllocations.load();
    for( int i = 0; i < 16; ++i ) exercise();
    auto retained = liveAllocations.load() - before;
    if( retained != 0 )
    {
      std::fprintf( stderr, "Unbalanced binding allocations: %lld\n", retained );
      return 1;
    }
    std::puts( "Borrowed blob streams retain exact bytes and release all measured allocations." );
    return 0;
  }
  catch( const std::exception& error )
  {
    std::fprintf( stderr, "%s\n", error.what() );
    return 1;
  }
}
