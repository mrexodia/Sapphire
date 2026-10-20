#ifndef XIV_EXD_EXD_H
#define XIV_EXD_EXD_H

#include <memory>
#include <map>
#include "File.h"
#include "Exd/Structs.h"
#include "Exh.h"

namespace xivps3::exd
{
  using Field = binary::Cell;
  struct ExdCacheEntry
  {
    std::shared_ptr< dat::File > file;
    size_t offset;
  };

  // Data for one language. Files are shared; decoded primary rows are cached.
  class Exd
  {
  public:
    Exd() = default;
    Exd( std::shared_ptr< Exh > header, const std::vector< std::shared_ptr< dat::File > >& files );
    ~Exd() = default;

    std::vector< Field > get_row( uint32_t id ) const;
    // subRow is a physical ordinal, NOT the stored subkey ID.
    std::vector< Field > get_row( uint32_t id, uint32_t subRow ) const;
    std::vector< uint16_t > get_subrow_keys( uint32_t id, uint32_t subRow ) const;
    size_t get_subrow_count( uint32_t id ) const;
    std::vector< uint32_t > get_ids() const;
    // Compatibility view: first subrow of each main ID, not all subrows.
    const std::map< uint32_t, std::vector< Field > >& get_rows() const;

    template< typename T >
    std::shared_ptr< Excel::Ps3::ExcelStruct< T > > get_row( uint32_t id, uint32_t subRow = 0 ) const
    {
      static_assert( std::is_trivially_copyable_v< T >, "Excel row views must be trivially copyable" );
      if( !_exh ) throw std::runtime_error( "Uninitialized sheet" );
      const auto& h = _exh->get_binary_header();
      if( sizeof( T ) != h.fixedSize )
        throw std::runtime_error( "Struct size " + std::to_string( sizeof( T ) ) +
                                  " does not match EXH fixed size " + std::to_string( h.fixedSize ) );
      const auto& entry = cache( id );
      const auto& bytes = pageBytes( *entry.file );
      const auto decoded = binary::row( h, bytes, id, entry.offset, subRow );
      const auto r = binary::layout( h, bytes, entry.offset );
      const size_t data = r.first + subRow * r.stride + 2 * ( h.keyCount - 1 );
      auto result = std::make_shared< Excel::Ps3::ExcelStruct< T > >();
      std::memcpy( result->ptr(), bytes.data() + data, sizeof( T ) );
      for( size_t i = 0; i < h.columns.size(); ++i )
      {
        const auto& c = h.columns[ i ];
        // Legacy Excel::Ps3 structs declare boolean bitfields in PS3 order.
        // On little-endian hosts their allocation order is reversed. Normalize
        // from the ORIGINAL byte on every visit (offsets may repeat), never
        // overwrite a shared byte with a single decoded bool.
        if( c.type >= 25 && c.type <= 32 )
        {
          const uint16_t endianProbe = 1;
          if( *reinterpret_cast< const uint8_t* >( &endianProbe ) == 1 )
          {
            uint8_t source = static_cast< uint8_t >( bytes[ data + c.offset ] ), reversed = 0;
            for( unsigned bit = 0; bit < 8; ++bit ) { reversed = static_cast< uint8_t >( ( reversed << 1 ) | ( source & 1 ) ); source >>= 1; }
            result->ptr()[ c.offset ] = reversed;
          }
          continue;
        }
        std::visit( [&]( const auto& value ) {
          using V = std::decay_t< decltype( value ) >;
          if constexpr( std::is_same_v< V, std::string > )
          {
            const auto stringIndex = static_cast< uint32_t >( result->_strings.size() );
            result->_strings.push_back( value );
            std::memcpy( result->ptr() + c.offset, &stringIndex, sizeof( stringIndex ) );
          }
          else if constexpr( std::is_same_v< V, binary::HalfBits > )
            std::memcpy( result->ptr() + c.offset, &value.bits, sizeof( value.bits ) );
          else
            std::memcpy( result->ptr() + c.offset, &value, sizeof( value ) );
        }, decoded.fields[ i ] );
      }
      return result;
    }

  private:
    static const binary::Bytes& pageBytes( const dat::File& file );
    const ExdCacheEntry& cache( uint32_t id ) const;
    mutable std::map< uint32_t, std::vector< Field > > _data;
    std::shared_ptr< Exh > _exh;
    std::map< uint32_t, ExdCacheEntry > _idCache;
  };
}
#endif
