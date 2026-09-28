#include "Manager/ItemIdAllocator.h"

#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>

using Sapphire::World::Manager::ItemIdAllocator;

int main()
{
  {
    ItemIdAllocator allocator;
    int loads = 0;
    assert( allocator.allocate( [&] { ++loads; return uint64_t{ 0 }; } ) == ItemIdAllocator::FirstId );
    assert( allocator.allocate( [&] { ++loads; return uint64_t{ 9000000 }; } ) == ItemIdAllocator::FirstId + 1 );
    assert( loads == 1 );
  }
  {
    ItemIdAllocator allocator;
    constexpr size_t count = 64;
    constexpr uint64_t maximum = 0x00600000;
    std::atomic< int > loads{ 0 };
    std::mutex outputMutex;
    std::vector< uint64_t > ids;
    std::vector< std::thread > threads;
    ids.reserve( count );
    threads.reserve( count );
    for( size_t i = 0; i < count; ++i )
    {
      threads.emplace_back( [&]
      {
        auto id = allocator.allocate( [&] { ++loads; return maximum; } );
        std::lock_guard< std::mutex > lock( outputMutex );
        ids.push_back( id );
      } );
    }
    for( auto& thread : threads )
      thread.join();
    std::sort( ids.begin(), ids.end() );
    assert( ids.size() == count && loads == 1 );
    for( size_t i = 0; i < count; ++i )
      assert( ids[ i ] == maximum + 1 + i );
  }
  {
    ItemIdAllocator allocator;
    bool threw = false;
    try
    {
      allocator.allocate( [] { return std::numeric_limits< uint64_t >::max(); } );
    }
    catch( const std::overflow_error& )
    {
      threw = true;
    }
    assert( threw );
  }
}
