#pragma once

#include <cstdint>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <utility>

namespace Sapphire::World::Manager
{

  // Serializes process-local item IDs so asynchronous inserts cannot make two
  // back-to-back allocations observe the same database MAX(ItemId).
  class ItemIdAllocator
  {
  public:
    static constexpr uint64_t FirstId = 0x00500001;

    template< typename LoadMaximum >
    uint64_t allocate( LoadMaximum&& loadMaximum )
    {
      std::lock_guard< std::mutex > lock( m_mutex );
      if( !m_initialized )
      {
        const uint64_t maximum = std::forward< LoadMaximum >( loadMaximum )();
        if( maximum == std::numeric_limits< uint64_t >::max() )
          throw std::overflow_error( "item ID space exhausted" );
        m_next = maximum < FirstId ? FirstId : maximum + 1;
        m_initialized = true;
      }
      if( m_next == std::numeric_limits< uint64_t >::max() )
        throw std::overflow_error( "item ID space exhausted" );
      return m_next++;
    }

  private:
    std::mutex m_mutex;
    uint64_t m_next{ 0 };
    bool m_initialized{ false };
  };

}
