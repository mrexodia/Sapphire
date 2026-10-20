#pragma once

// Shared PS3 Monitor EXH v3 / EXD decoder. No GUI, JSON or host-ABI dependency.
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <variant>
#include <vector>

namespace xivps3::exd::binary
{
  using Bytes = std::vector< char >;
  struct HalfBits // Retain F16 losslessly; no semantic conversion.
  {
    uint16_t bits;
    bool operator==( const HalfBits& other ) const { return bits == other.bits; }
    bool operator!=( const HalfBits& other ) const { return !( *this == other ); }
  };
  using Cell = std::variant< std::string, bool, int8_t, uint8_t, int16_t, uint16_t,
                             int32_t, uint32_t, float, uint64_t, int64_t, HalfBits >;

  inline void require( const Bytes& b, size_t p, size_t n )
  {
    if( p > b.size() || n > b.size() - p ) throw std::runtime_error( "Truncated data at " + std::to_string( p ) );
  }

  inline uint64_t be( const Bytes& b, size_t p, size_t n )
  {
    if( n > 8 ) throw std::runtime_error( "Integer width exceeds 64 bits" );
    require( b, p, n );
    uint64_t v = 0;
    for( size_t i = 0; i < n; ++i ) v = ( v << 8 ) | static_cast< uint8_t >( b[ p + i ] );
    return v;
  }

  inline std::string string( const Bytes& b, size_t p, size_t end )
  {
    if( end > b.size() || p >= end ) throw std::runtime_error( "String offset outside row" );
    size_t q = p;
    while( q < end && b[ q ] ) ++q;
    if( q == end ) throw std::runtime_error( "Unterminated string" );
    return { b.begin() + p, b.begin() + q };
  }

  inline void magic( const Bytes& b, const char* value )
  {
    require( b, 0, 32 );
    if( std::memcmp( b.data(), value, 4 ) ) throw std::runtime_error( std::string( "Expected " ) + value );
  }

  inline const char* typeName( unsigned type )
  {
    static const char* names[] = { "string", "bool", "i8", "u8", "i16", "u16", "i32", "u32",
                                 "f16", "f32", "i64", "u64", "binary" };
    if( type < 13 ) return names[ type ];
    if( type >= 25 && type <= 32 ) return "packed_bool";
    return "unknown";
  }

  inline size_t width( unsigned type )
  {
    if( type == 0 || type == 6 || type == 7 || type == 9 ) return 4;
    if( type == 4 || type == 5 || type == 8 ) return 2;
    if( type == 10 || type == 11 ) return 8;
    if( ( type >= 1 && type <= 3 ) || ( type >= 25 && type <= 32 ) ) return 1;
    throw std::runtime_error( "Unsupported cell type " + std::to_string( type ) );
  }

  struct Column { unsigned type; size_t offset; };
  struct Page { uint32_t start; uint32_t count; };
  struct Header
  {
    unsigned version, fixedSize, keyCount;
    uint32_t rowCount;
    std::vector< Column > columns;
    std::vector< Page > pages;
    std::vector< unsigned > languages;

    explicit Header( const Bytes& b )
    {
      magic( b, "EXHF" );
      version = static_cast< unsigned >( be( b, 4, 2 ) );
      if( version != 3 ) throw std::runtime_error( "Unsupported EXH version " + std::to_string( version ) );
      fixedSize = static_cast< unsigned >( be( b, 6, 2 ) );
      keyCount = static_cast< unsigned >( be( b, 16, 2 ) );
      // GetSubkeyCount returns total keys; ExcelSheet subtracts the main row key.
      if( keyCount < 1 || keyCount > 4 ) throw std::runtime_error( "Unsupported key count " + std::to_string( keyCount ) );
      rowCount = static_cast< uint32_t >( be( b, 20, 4 ) );
      size_t p = 32;
      for( size_t i = 0; i < be( b, 8, 2 ); ++i, p += 4 )
        columns.push_back( { static_cast< unsigned >( be( b, p, 2 ) ), static_cast< size_t >( be( b, p + 2, 2 ) ) } );
      for( size_t i = 0; i < be( b, 10, 2 ); ++i, p += 8 )
        pages.push_back( { static_cast< uint32_t >( be( b, p, 4 ) ), static_cast< uint32_t >( be( b, p + 4, 4 ) ) } );
      for( size_t i = 0; i < be( b, 12, 2 ); ++i, p += 2 )
      {
        require( b, p, 2 ); // language byte followed by padding, not BE uint16
        languages.push_back( static_cast< uint8_t >( b[ p ] ) );
      }
    }
  };

  template< typename T > inline T signedBits( uint64_t value )
  {
    auto bits = static_cast< std::make_unsigned_t< T > >( value );
    T result;
    std::memcpy( &result, &bits, sizeof( result ) );
    return result;
  }

  inline Cell cell( const Bytes& b, const Column& c, size_t data, size_t fixedEnd, size_t strings, size_t end )
  {
    if( data > fixedEnd || c.offset > fixedEnd - data ) throw std::runtime_error( "Cell outside fixed data" );
    const auto p = data + c.offset;
    const auto n = width( c.type );
    if( n > fixedEnd - p ) throw std::runtime_error( "Cell outside fixed data" );
    const auto v = be( b, p, n );
    switch( c.type )
    {
      case 0:
        if( strings > end || v >= end - strings ) throw std::runtime_error( "String offset outside row" );
        return string( b, strings + static_cast< size_t >( v ), end );
      case 1: return v != 0;
      case 2: return signedBits< int8_t >( v );
      case 3: return static_cast< uint8_t >( v );
      case 4: return signedBits< int16_t >( v );
      case 5: return static_cast< uint16_t >( v );
      case 6: return signedBits< int32_t >( v );
      case 7: return static_cast< uint32_t >( v );
      case 8: return HalfBits{ static_cast< uint16_t >( v ) };
      case 9:
      {
        uint32_t bits = static_cast< uint32_t >( v );
        float f;
        std::memcpy( &f, &bits, sizeof( f ) );
        return f;
      }
      case 10: return signedBits< int64_t >( v );
      case 11: return v;
      default: return ( v & ( uint64_t{ 1 } << ( c.type - 25 ) ) ) != 0;
    }
  }

  struct IndexEntry { uint32_t id; size_t offset; };
  inline std::vector< IndexEntry > index( const Bytes& b )
  {
    magic( b, "EXDF" );
    const auto size = static_cast< size_t >( be( b, 8, 4 ) );
    if( size % 8 ) throw std::runtime_error( "Misaligned EXD index" );
    require( b, 32, size );
    std::vector< IndexEntry > entries;
    entries.reserve( size / 8 );
    for( size_t i = 32; i < 32 + size; i += 8 )
    {
      const auto p = static_cast< size_t >( be( b, i + 4, 4 ) );
      if( p < 32 + size ) throw std::runtime_error( "Row overlaps index" );
      require( b, p, 6 );
      entries.push_back( { static_cast< uint32_t >( be( b, i, 4 ) ), p } );
    }
    return entries;
  }

  struct RowLayout { size_t count, stride, first, strings, end; };
  inline RowLayout layout( const Header& h, const Bytes& b, size_t p )
  {
    require( b, p, 6 );
    const auto length = static_cast< size_t >( be( b, p, 4 ) );
    const auto count = static_cast< size_t >( be( b, p + 4, 2 ) );
    require( b, p + 6, length );
    const size_t stride = h.fixedSize + 2 * ( h.keyCount - 1 );
    if( !stride || count > length / stride ) throw std::runtime_error( "Subrows exceed row length" );
    return { count, stride, p + 6, p + 6 + count * stride, p + 6 + length };
  }

  struct Row { uint32_t id; std::vector< uint16_t > subkeys; std::vector< Cell > fields; };
  inline Row row( const Header& h, const Bytes& b, uint32_t id, size_t p, size_t ordinal )
  {
    const auto r = layout( h, b, p );
    if( ordinal >= r.count ) throw std::out_of_range( "Subrow ordinal outside row" );
    const size_t sub = r.first + ordinal * r.stride;
    const size_t data = sub + 2 * ( h.keyCount - 1 );
    Row out{ id, {}, {} };
    for( unsigned k = 1; k < h.keyCount; ++k )
      out.subkeys.push_back( static_cast< uint16_t >( be( b, sub + 2 * ( k - 1 ), 2 ) ) );
    out.fields.reserve( h.columns.size() );
    for( const auto& c : h.columns ) out.fields.push_back( cell( b, c, data, data + h.fixedSize, r.strings, r.end ) );
    return out;
  }

  template< typename Visitor > void rows( const Header& h, const Bytes& b, Visitor visit )
  {
    for( const auto& entry : index( b ) )
      for( size_t s = 0, count = layout( h, b, entry.offset ).count; s < count; ++s )
        visit( row( h, b, entry.id, entry.offset, s ) );
  }
}
