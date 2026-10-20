#include "ExdCat.h"
#include "GameData.h"
#include <algorithm>

namespace xivps3::exd
{
  Cat::Cat( dat::GameData& gameData, const std::string& name ) : _name( name ), _game_data( gameData )
  {
    _header = std::make_shared< Exh >( *gameData.getFile( "exd/" + name + ".exh" ) );
  }

  Cat::~Cat() = default;
  const std::string& Cat::get_name() const { return _name; }
  const Exh& Cat::get_header() const { return *_header; }

  const Exd& Cat::get_data_ln( Language language ) const
  {
    const auto& declared = _header->get_languages();
    if( std::find( declared.begin(), declared.end(), language ) == declared.end() )
      throw std::runtime_error( "Language absent from sheet: " + std::to_string( static_cast< unsigned >( language ) ) );
    static const char* suffixes[] = { "", "_ja", "_en", "_de", "_fr", "_chs", "_cht", "_ko" };
    if( static_cast< unsigned >( language ) >= 8 ) throw std::runtime_error( "Unknown EXH language" );
    std::lock_guard< std::mutex > lock( _data_mutex );
    auto it = _data.find( language );
    if( it == _data.end() )
    {
      std::vector< std::shared_ptr< dat::File > > files;
      for( const auto& page : _header->get_exd_defs() )
        files.push_back( _game_data.getFile( "exd/" + _name + "_" + std::to_string( page.start_id ) + suffixes[ language ] + ".exd" ) );
      it = _data.emplace( language, std::make_unique< Exd >( _header, files ) ).first;
    }
    return *it->second;
  }

  const Exd& Cat::get_data( Language language ) const
  {
    const auto& declared = _header->get_languages();
    // Only fallback to an explicitly language-neutral sheet, never hide a
    // missing requested page by choosing an unrelated language.
    if( std::find( declared.begin(), declared.end(), language ) == declared.end() ) language = Language::none;
    return get_data_ln( language );
  }
}
