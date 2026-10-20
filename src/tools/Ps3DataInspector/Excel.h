#pragma once

// JSON presentation adapter; decoding is shared with ToolkitPs3's xivdatps3.
#include <ExcelBinary.h>
#include <nlohmann/json.hpp>
#include <cmath>

namespace Ps3Excel
{
  namespace Binary = xivps3::exd::binary;
  using Json = nlohmann::ordered_json;
  using Bytes = Binary::Bytes;
  using Column = Binary::Column;
  using Page = Binary::Page;
  using Binary::require;
  using Binary::be;
  using Binary::string;
  using Binary::magic;
  using Binary::typeName;
  using Binary::width;

  inline std::string hex( const Bytes& b, size_t p, size_t n )
  {
    require( b, p, n );
    constexpr char digits[] = "0123456789abcdef";
    std::string out;
    for( size_t i = 0; i < n; ++i )
    {
      auto c = static_cast< uint8_t >( b[ p + i ] );
      out += digits[ c >> 4 ]; out += digits[ c & 15 ];
    }
    return out;
  }

  struct Header : Binary::Header
  {
    using Binary::Header::Header;
    Json schema() const
    {
      Json out = { { "version", version }, { "fixed_size", fixedSize }, { "key_count", keyCount },
                   { "row_count", rowCount }, { "languages", languages }, { "columns", Json::array() },
                   { "pages", Json::array() } };
      for( const auto& c : columns ) out[ "columns" ].push_back( {
        { "type", c.type }, { "type_name", typeName( c.type ) }, { "offset", c.offset } } );
      for( const auto& p : pages ) out[ "pages" ].push_back( { { "start", p.start }, { "count", p.count } } );
      return out;
    }
  };

  inline Json jsonCell( const Binary::Cell& value )
  {
    return std::visit( []( const auto& v ) -> Json {
      using T = std::decay_t< decltype( v ) >;
      if constexpr( std::is_same_v< T, std::string > )
      {
        Bytes bytes( v.begin(), v.end() );
        return Json{ { "text", v }, { "bytes_hex", hex( bytes, 0, bytes.size() ) } };
      }
      else if constexpr( std::is_same_v< T, Binary::HalfBits > ) return Json{ { "f16_bits", v.bits } };
      else if constexpr( std::is_same_v< T, float > )
      {
        if( std::isfinite( v ) ) return v;
        uint32_t bits;
        std::memcpy( &bits, &v, sizeof( bits ) );
        return Json{ { "f32_bits", bits } };
      }
      else return v;
    }, value );
  }

  inline Json cell( const Bytes& b, const Column& c, size_t data, size_t strings, size_t end )
  {
    return jsonCell( Binary::cell( b, c, data, strings, strings, end ) );
  }

  template< typename Visitor > void rows( const Header& h, const Bytes& b, Visitor visit )
  {
    Binary::rows( h, b, [&]( const Binary::Row& r ) {
      Json out = { { "id", r.id }, { "subkeys", r.subkeys }, { "fields", Json::array() } };
      for( const auto& field : r.fields ) out[ "fields" ].push_back( jsonCell( field ) );
      visit( out );
    } );
  }
}
