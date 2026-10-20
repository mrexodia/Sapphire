#include "Exd.h"

namespace xivps3::exd
{
  const binary::Bytes& Exd::pageBytes( const dat::File& file )
  {
    const auto& sections = file.get_data_sections();
    if( sections.size() != 1 ) throw std::runtime_error( "EXD requires one data section" );
    return sections.front();
  }

  Exd::Exd( std::shared_ptr< Exh > header, const std::vector< std::shared_ptr< dat::File > >& files ) : _exh( std::move( header ) )
  {
    if( !_exh ) throw std::runtime_error( "Missing EXH" );
    for( const auto& file : files )
    {
      if( !file ) throw std::runtime_error( "Missing EXD page" );
      const auto& bytes = pageBytes( *file );
      for( const auto& entry : binary::index( bytes ) )
      {
        binary::layout( _exh->get_binary_header(), bytes, entry.offset );
        if( !_idCache.emplace( entry.id, ExdCacheEntry{ file, entry.offset } ).second )
          throw std::runtime_error( "Duplicate EXD main ID: " + std::to_string( entry.id ) );
      }
    }
  }

  const ExdCacheEntry& Exd::cache( uint32_t id ) const
  {
    const auto it = _idCache.find( id );
    if( it == _idCache.end() ) throw std::out_of_range( "Id not found: " + std::to_string( id ) );
    return it->second;
  }

  std::vector< Field > Exd::get_row( uint32_t id ) const { return get_row( id, 0 ); }
  std::vector< Field > Exd::get_row( uint32_t id, uint32_t subRow ) const
  {
    if( subRow == 0 )
    {
      const auto it = _data.find( id );
      if( it != _data.end() ) return it->second;
    }
    const auto& entry = cache( id );
    auto decoded = binary::row( _exh->get_binary_header(), pageBytes( *entry.file ), id, entry.offset, subRow );
    if( subRow == 0 ) _data.emplace( id, decoded.fields );
    return decoded.fields;
  }

  std::vector< uint16_t > Exd::get_subrow_keys( uint32_t id, uint32_t subRow ) const
  {
    const auto& entry = cache( id );
    const auto& h = _exh->get_binary_header();
    const auto& bytes = pageBytes( *entry.file );
    const auto r = binary::layout( h, bytes, entry.offset );
    if( subRow >= r.count ) throw std::out_of_range( "Subrow ordinal outside row" );
    std::vector< uint16_t > keys;
    for( unsigned k = 1; k < h.keyCount; ++k )
      keys.push_back( static_cast< uint16_t >( binary::be( bytes, r.first + subRow * r.stride + 2 * ( k - 1 ), 2 ) ) );
    return keys;
  }

  size_t Exd::get_subrow_count( uint32_t id ) const
  {
    const auto& entry = cache( id );
    return binary::layout( _exh->get_binary_header(), pageBytes( *entry.file ), entry.offset ).count;
  }

  std::vector< uint32_t > Exd::get_ids() const
  {
    std::vector< uint32_t > ids;
    ids.reserve( _idCache.size() );
    for( const auto& entry : _idCache ) ids.push_back( entry.first );
    return ids;
  }

  const std::map< uint32_t, std::vector< Field > >& Exd::get_rows() const
  {
    for( const auto& entry : _idCache ) get_row( entry.first );
    return _data;
  }
}
