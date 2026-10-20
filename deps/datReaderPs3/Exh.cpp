#include "Exh.h"
#include "File.h"
#include "ExdCat.h"

namespace xivps3::exd
{
  namespace
  {
    const binary::Bytes& headerBytes( const dat::File& file )
    {
      const auto& sections = file.get_data_sections();
      if( sections.size() != 1 ) throw std::runtime_error( "EXH requires one data section" );
      return sections.front();
    }
  }

  Exh::Exh( const dat::File& file ) : Exh( headerBytes( file ) ) {}

  Exh::Exh( const binary::Bytes& bytes ) : _binary( bytes )
  {
    std::memcpy( _header.magic, "EXHF", 4 );
    _header.unknown = static_cast< uint16_t >( _binary.version );
    _header.data_offset = static_cast< uint16_t >( _binary.fixedSize );
    _header.field_count = static_cast< uint16_t >( _binary.columns.size() );
    _header.exd_count = static_cast< uint16_t >( _binary.pages.size() );
    _header.language_count = static_cast< uint16_t >( _binary.languages.size() );
    _header.unknown1 = static_cast< uint16_t >( binary::be( bytes, 14, 2 ) );
    _header.variant = static_cast< uint8_t >( _binary.keyCount );
    for( const auto& c : _binary.columns )
    {
      ExhMember member{ static_cast< DataType >( c.type ), static_cast< uint16_t >( c.offset ) };
      _exh_defs.push_back( member ); // retain all columns, including repeated offsets
      _members[ member.offset ] = member;
    }
    for( const auto& p : _binary.pages ) _exd_defs.push_back( { p.start, p.count } );
    for( auto language : _binary.languages ) _languages.push_back( static_cast< Language >( language ) );
  }

  Exh::~Exh() = default;
  const binary::Header& Exh::get_binary_header() const { return _binary; }
  const ExhHeader& Exh::get_header() const { return _header; }
  const std::vector< ExhExdDef >& Exh::get_exd_defs() const { return _exd_defs; }
  const std::vector< Language >& Exh::get_languages() const { return _languages; }
  const std::map< uint32_t, ExhMember >& Exh::get_members() const { return _members; }
  const std::vector< ExhMember >& Exh::get_exh_members() const { return _exh_defs; }
}
