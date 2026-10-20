// Headless PS3 SqPack inventory and extraction. No game/server initialization.
#include "Excel.h"
#include <GameData.h>
#include <Index.h>
#include <Dat.h>
#include <File.h>
#include <Exd.h>
#include <ExdData.h>
#include <ExdCat.h>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace fs = std::filesystem;
using Json = nlohmann::ordered_json;
using Bytes = std::vector< char >;

static void saveJson( const fs::path& path, const Json& value )
{
  std::ofstream out( path, std::ios::binary );
  if( !out ) throw std::runtime_error( "Cannot write " + path.string() );
  out << value.dump( 2, ' ', false, Json::error_handler_t::replace ) << '\n';
  if( !out ) throw std::runtime_error( "Write failed: " + path.string() );
}

static void exportAsset( const xivps3::dat::File& file, const fs::path& path )
{
  std::ofstream out( path, std::ios::binary );
  if( !out ) throw std::runtime_error( "Cannot write " + path.string() );
  for( const auto& section : file.get_data_sections() ) out.write( section.data(), section.size() );
  if( !out ) throw std::runtime_error( "Write failed: " + path.string() );
}

static Bytes readAsset( xivps3::dat::GameData& data, const std::string& path )
{
  auto file = data.getFile( path );
  if( file->get_type() != xivps3::dat::FileType::standard || file->get_data_sections().size() != 1 )
    throw std::runtime_error( "Expected one standard data section: " + path );
  return file->get_data_sections().front();
}

static void inventory( const fs::path& root, const fs::path& output )
{
  std::vector< fs::path > paths;
  for( const auto& entry : fs::recursive_directory_iterator( root ) )
    if( entry.is_regular_file() ) paths.push_back( entry.path() );
  std::sort( paths.begin(), paths.end() );
  Json result = { { "root", root.generic_string() }, { "loose_files", Json::array() },
                  { "archives", Json::array() } };
  size_t count = 0, errors = 0;
  for( const auto& path : paths )
  {
    result[ "loose_files" ].push_back( { { "path", fs::relative( path, root ).generic_string() },
                                        { "size", fs::file_size( path ) } } );
    if( path.extension() != ".index" ) continue;
    Json archive = { { "path", fs::relative( path, root ).generic_string() } };
    try
    {
      xivps3::dat::Index index( path );
      archive[ "dat_count" ] = index.getDatCount();
      archive[ "data_files" ] = Json::array();
      for( uint32_t i = 0; i < index.getDatCount(); ++i )
      {
        auto dat = path;
        dat.replace_extension( ".dat" + std::to_string( i ) );
        auto encrypted = fs::path( dat.string() + ".sdat" );
        archive[ "data_files" ].push_back( {
          { "path", fs::relative( dat, root ).generic_string() }, { "present", fs::exists( dat ) },
          { "encrypted_sdat_present", fs::exists( encrypted ) } } );
      }
      std::vector< xivps3::dat::Index::HashTableEntry > entries;
      for( const auto& [ dir, files ] : index.getHashTable() )
        for( const auto& [ name, entry ] : files ) entries.push_back( entry );
      std::sort( entries.begin(), entries.end(), []( const auto& a, const auto& b )
        { return std::tie( a.dirHash, a.filenameHash ) < std::tie( b.dirHash, b.filenameHash ); } );
      archive[ "entries" ] = Json::array();
      for( const auto& entry : entries )
        archive[ "entries" ].push_back( { { "directory_hash", entry.dirHash },
          { "filename_hash", entry.filenameHash }, { "dat", entry.datNum },
          { "offset", entry.datOffset } } );
      count += entries.size();
    }
    catch( const std::exception& e ) { archive[ "error" ] = e.what(); ++errors; }
    result[ "archives" ].push_back( std::move( archive ) );
  }
  result[ "entry_count" ] = count;
  result[ "error_count" ] = errors;
  saveJson( output, result );
  std::cerr << count << " archive entries, " << errors << " index errors\n";
  if( errors ) throw std::runtime_error( "Incomplete inventory; see error entries in output" );
}

// The monitor's Scene_t, SGTimelineFolder_t, SGSettings_t and SGTimeline_t layouts.
// General-purpose slots map to MemberID; their order need not equal the timeline array order.
static Json sharedGroupTimelines( const Bytes& b )
{
  Ps3Excel::magic( b, "SGB1" );
  if( Ps3Excel::be( b, 4, 4 ) != b.size() || Ps3Excel::be( b, 8, 4 ) != 1 ||
      std::memcmp( b.data() + 12, "SCN1", 4 ) )
    throw std::runtime_error( "Unsupported SGB container" );
  constexpr size_t scene = 20;
  Ps3Excel::require( b, scene, 68 );
  auto relative = [&]( size_t base, size_t field ) -> size_t
  {
    int64_t p = static_cast< int64_t >( base ) + static_cast< int32_t >( Ps3Excel::be( b, field, 4 ) );
    if( p < 0 || static_cast< uint64_t >( p ) >= b.size() ) throw std::runtime_error( "Invalid SGB relative offset" );
    return static_cast< size_t >( p );
  };
  size_t folder = relative( scene, scene + 16 );
  size_t settings = relative( scene, scene + 32 );
  Ps3Excel::require( b, settings, 36 );
  size_t count = static_cast< size_t >( Ps3Excel::be( b, folder + 4, 4 ) );
  size_t base = relative( folder, folder );
  if( count > b.size() / 44 ) throw std::runtime_error( "Invalid SGB timeline count" );
  Ps3Excel::require( b, base, count * 44 );
  Json out = { { "timelines", Json::array() }, { "general_purpose_slots", Json::array() } };
  for( size_t i = 0; i < count; ++i )
  {
    size_t p = base + i * 44;
    out[ "timelines" ].push_back( {
      { "member_id", Ps3Excel::be( b, p, 4 ) },
      { "name", Ps3Excel::string( b, relative( p, p + 4 ), b.size() ) },
      { "timeline_id", Ps3Excel::be( b, p + 28, 4 ) },
      { "auto_play", Ps3Excel::be( b, p + 32, 1 ) },
      { "loop_playback", Ps3Excel::be( b, p + 33, 1 ) },
      { "collision_state", Ps3Excel::be( b, p + 36, 4 ) } } );
  }
  for( size_t i = 0; i < 16; ++i )
  {
    auto member = Ps3Excel::be( b, settings + 5 + i, 1 );
    Json slot = { { "index", i }, { "mask", uint32_t{ 1 } << i }, { "member_id", member } };
    for( const auto& timeline : out[ "timelines" ] )
      if( member && timeline[ "member_id" ] == member ) slot[ "name" ] = timeline[ "name" ];
    out[ "general_purpose_slots" ].push_back( std::move( slot ) );
  }
  return out;
}

static std::string languageSuffix( unsigned language )
{
  static const char* codes[] = { "", "_ja", "_en", "_de", "_fr", "_chs", "_cht", "_ko" };
  if( language >= 8 ) throw std::runtime_error( "Unknown language " + std::to_string( language ) );
  return codes[ language ];
}

static Json inspectSheet( xivps3::dat::GameData& data, const std::string& name, bool dump, unsigned language )
{
  Ps3Excel::Header header( readAsset( data, "exd/" + name + ".exh" ) );
  Json out = header.schema();
  out[ "name" ] = name;
  if( !dump ) return out;
  if( std::find( header.languages.begin(), header.languages.end(), language ) == header.languages.end() )
    throw std::runtime_error( "Language not present in sheet" );
  out[ "rows" ] = Json::array();
  for( const auto& page : header.pages )
  {
    auto path = "exd/" + name + "_" + std::to_string( page.start ) + languageSuffix( language ) + ".exd";
    Ps3Excel::rows( header, readAsset( data, path ), [&]( const Json& row ) { out[ "rows" ].push_back( row ); } );
  }
  return out;
}

struct SemanticLabel
{
  std::string name;
  std::string confidence{ "physical_only" };
};
using SemanticLabels = std::unordered_map< std::string, std::vector< SemanticLabel > >;

static SemanticLabels loadSemanticLabels( const fs::path& path )
{
  if( path.empty() ) return {};
  std::ifstream input( path, std::ios::binary );
  if( !input ) throw std::runtime_error( "Cannot read semantic labels: " + path.string() );
  Json source;
  input >> source;
  SemanticLabels labels;
  if( source.is_array() )
  {
    for( const auto& sheet : source )
    {
      auto& fields = labels[ sheet.at( "sheet" ).get< std::string >() ];
      for( const auto& column : sheet.at( "columns" ) )
      {
        const auto index = column.at( "column" ).get< size_t >();
        if( fields.size() <= index ) fields.resize( index + 1 );
        const auto& candidates = column.at( "debug_field_candidates" );
        if( candidates.size() == 1 ) fields[ index ] = {
          candidates.front().get< std::string >(), "metadata_candidate" };
      }
    }
  }
  else if( source.is_object() && source.value( "schema_version", 0 ) == 1 && source.contains( "sheets" ) )
  {
    for( const auto& sheet : source.at( "sheets" ) )
    {
      auto& fields = labels[ sheet.at( "name" ).get< std::string >() ];
      for( const auto& field : sheet.at( "fields" ) )
      {
        const auto index = field.at( "column" ).get< size_t >();
        if( fields.size() <= index ) fields.resize( index + 1 );
        fields[ index ].name = field.at( "name" ).get< std::string >();
        for( const auto& label : field.value( "labels", Json::array() ) )
          if( label.value( "name", "" ) == fields[ index ].name )
          {
            fields[ index ].confidence = label.value( "confidence", "candidate" );
            break;
          }
      }
    }
  }
  else throw std::runtime_error( "Unsupported semantic-label JSON format" );
  return labels;
}

static std::string lowerAscii( std::string value )
{
  std::transform( value.begin(), value.end(), value.begin(), []( unsigned char c ) {
    return static_cast< char >( std::tolower( c ) );
  } );
  return value;
}

static SemanticLabel fieldLabel( const SemanticLabels& labels, const std::string& sheet, size_t column )
{
  auto found = labels.find( sheet );
  if( found != labels.end() && column < found->second.size() && !found->second[ column ].name.empty() )
    return found->second[ column ];
  return { "column_" + std::to_string( column ), "physical_only" };
}

static bool integralValue( const Ps3Excel::Binary::Cell& cell, int64_t& signedValue, uint64_t& unsignedValue,
                           bool& isSigned )
{
  return std::visit( [&]( const auto& value ) {
    using T = std::decay_t< decltype( value ) >;
    if constexpr( std::is_integral_v< T > && !std::is_same_v< T, bool > )
    {
      isSigned = std::is_signed_v< T >;
      if constexpr( std::is_signed_v< T > ) signedValue = static_cast< int64_t >( value );
      else unsignedValue = static_cast< uint64_t >( value );
      return true;
    }
    return false;
  }, cell );
}

static Json compactCell( const Ps3Excel::Binary::Cell& cell )
{
  return std::visit( []( const auto& value ) -> Json {
    using T = std::decay_t< decltype( value ) >;
    if constexpr( std::is_same_v< T, Ps3Excel::Binary::HalfBits > ) return Json{ { "f16", value.bits } };
    else if constexpr( std::is_same_v< T, float > )
    {
      if( std::isfinite( value ) ) return value;
      uint32_t bits;
      std::memcpy( &bits, &value, sizeof( bits ) );
      return Json{ { "f32", bits } };
    }
    else if constexpr( std::is_same_v< T, int8_t > || std::is_same_v< T, uint8_t > ) return int( value );
    else return value;
  }, cell );
}

static int32_t signedBe32( const Ps3Excel::Bytes& bytes, size_t offset )
{
  return Ps3Excel::Binary::signedBits< int32_t >( Ps3Excel::be( bytes, offset, 4 ) );
}

static size_t relativeOffset( const Ps3Excel::Bytes& bytes, size_t base, size_t field )
{
  const auto relative = static_cast< int64_t >( signedBe32( bytes, field ) );
  const auto target = static_cast< int64_t >( base ) + relative;
  if( target < 0 || static_cast< uint64_t >( target ) >= bytes.size() )
    throw std::runtime_error( "Relative offset outside LVB" );
  return static_cast< size_t >( target );
}

static const char* lgbTypeName( uint32_t type )
{
  switch( type )
  {
    case 1: return "BgParts";
    case 6: return "SharedGroup";
    case 8: return "EventNpc";
    case 9: return "BattleNpc";
    case 40: return "PopRange";
    case 41: return "ExitRange";
    case 43: return "MapRange";
    case 45: return "EventObject";
    case 66: return "ServerPath";
    default: return "Other";
  }
}

static Json inspectLgb( const Ps3Excel::Bytes& bytes )
{
  Ps3Excel::require( bytes, 0, 36 );
  if( std::memcmp( bytes.data(), "LGB1", 4 ) || std::memcmp( bytes.data() + 12, "LGP1", 4 ) )
    throw std::runtime_error( "Invalid LGB container" );
  const auto fileSize = static_cast< size_t >( Ps3Excel::be( bytes, 4, 4 ) );
  if( fileSize != bytes.size() ) throw std::runtime_error( "LGB size mismatch" );
  constexpr size_t table = 36;
  const auto groupCount = static_cast< size_t >( Ps3Excel::be( bytes, 32, 4 ) );
  if( groupCount > bytes.size() / 4 ) throw std::runtime_error( "Invalid LGB group count" );
  Ps3Excel::require( bytes, table, groupCount * 4 );
  Json result = { { "groups", Json::array() } };
  for( size_t groupIndex = 0; groupIndex < groupCount; ++groupIndex )
  {
    const auto group = relativeOffset( bytes, table, table + groupIndex * 4 );
    Ps3Excel::require( bytes, group, 52 );
    const auto entries = relativeOffset( bytes, group, group + 8 );
    const auto entryCount = static_cast< size_t >( Ps3Excel::be( bytes, group + 12, 4 ) );
    if( entryCount > bytes.size() / 4 ) throw std::runtime_error( "Invalid LGB entry count" );
    Ps3Excel::require( bytes, entries, entryCount * 4 );
    Json groupJson = { { "id", Ps3Excel::be( bytes, group, 4 ) },
                       { "name", Ps3Excel::string( bytes, relativeOffset( bytes, group, group + 4 ), bytes.size() ) },
                       { "entries", Json::array() } };
    for( size_t entryIndex = 0; entryIndex < entryCount; ++entryIndex )
    {
      const auto entry = relativeOffset( bytes, entries, entries + entryIndex * 4 );
      Ps3Excel::require( bytes, entry, 48 );
      const auto type = static_cast< uint32_t >( Ps3Excel::be( bytes, entry, 4 ) );
      Json item = { { "type", type }, { "type_name", lgbTypeName( type ) },
                    { "instance_id", Ps3Excel::be( bytes, entry + 4, 4 ) },
                    { "name", Ps3Excel::string( bytes, relativeOffset( bytes, entry, entry + 8 ), bytes.size() ) } };
      if( type == 1 || type == 6 )
      {
        Ps3Excel::require( bytes, entry, 52 );
        const auto pathOffset = signedBe32( bytes, entry + 48 );
        if( pathOffset ) item[ type == 6 ? "sgb_path" : "asset_path" ] =
          Ps3Excel::string( bytes, relativeOffset( bytes, entry, entry + 48 ), bytes.size() );
      }
      else if( type == 8 || type == 9 || type == 45 )
      {
        Ps3Excel::require( bytes, entry, 52 );
        item[ "base_id" ] = Ps3Excel::be( bytes, entry + 48, 4 );
      }
      groupJson[ "entries" ].push_back( std::move( item ) );
    }
    result[ "groups" ].push_back( std::move( groupJson ) );
  }
  return result;
}

static Json inspectLvb( const Ps3Excel::Bytes& bytes )
{
  Ps3Excel::require( bytes, 0, 84 );
  if( std::memcmp( bytes.data(), "LVB1", 4 ) || std::memcmp( bytes.data() + 12, "SCN1", 4 ) )
    throw std::runtime_error( "Invalid LVB container" );
  const auto fileSize = static_cast< size_t >( Ps3Excel::be( bytes, 4, 4 ) );
  if( fileSize != bytes.size() ) throw std::runtime_error( "LVB size mismatch" );
  constexpr size_t data = 20;
  const auto layerFolder = relativeOffset( bytes, data, data + 12 );
  const auto lgbList = relativeOffset( bytes, data, data + 20 );
  const auto lgbCount = static_cast< size_t >( Ps3Excel::be( bytes, data + 24, 4 ) );
  if( lgbCount > bytes.size() / 4 ) throw std::runtime_error( "Invalid LVB LGB count" );
  Ps3Excel::require( bytes, lgbList, lgbCount * 4 );
  Json result = { { "lgb_paths", Json::array() }, { "layer_sets", Json::array() } };
  for( size_t i = 0; i < lgbCount; ++i )
    result[ "lgb_paths" ].push_back( Ps3Excel::string( bytes, relativeOffset( bytes, lgbList, lgbList + i * 4 ), bytes.size() ) );

  Ps3Excel::require( bytes, layerFolder, 8 );
  const auto layerCount = static_cast< size_t >( Ps3Excel::be( bytes, layerFolder + 4, 4 ) );
  const auto layers = relativeOffset( bytes, layerFolder, layerFolder );
  if( layerCount > bytes.size() / 24 ) throw std::runtime_error( "Invalid LVB layer-set count" );
  Ps3Excel::require( bytes, layers, layerCount * 24 );
  for( size_t i = 0; i < layerCount; ++i )
  {
    const auto entry = layers + i * 24;
    const auto referenceCount = static_cast< size_t >( Ps3Excel::be( bytes, entry + 12, 4 ) );
    Json layer = { { "layer_set_id", Ps3Excel::be( bytes, entry + 4, 4 ) },
                   { "territory_type_id", Ps3Excel::be( bytes, entry + 16, 4 ) },
                   { "name", Ps3Excel::string( bytes, relativeOffset( bytes, entry, entry + 20 ), bytes.size() ) },
                   { "references", Json::array() } };
    const auto navOffset = signedBe32( bytes, entry );
    if( navOffset ) layer[ "navmesh_path" ] = Ps3Excel::string( bytes, relativeOffset( bytes, entry, entry ), bytes.size() );
    if( referenceCount )
    {
      const auto references = relativeOffset( bytes, entry, entry + 8 );
      if( referenceCount > bytes.size() / 40 ) throw std::runtime_error( "Invalid LVB layer reference count" );
      Ps3Excel::require( bytes, references, referenceCount * 40 );
      for( size_t reference = 0; reference < referenceCount; ++reference )
      {
        const auto item = references + reference * 40;
        Ps3Excel::require( bytes, item, 40 );
        size_t end = item + 8;
        while( end < item + 40 && bytes[ end ] ) ++end;
        layer[ "references" ].push_back( {
          { "layer_set_id", Ps3Excel::be( bytes, item, 4 ) },
          { "territory_type_id", Ps3Excel::be( bytes, item + 4, 4 ) },
          { "name", std::string( bytes.begin() + item + 8, bytes.begin() + end ) } } );
      }
    }
    result[ "layer_sets" ].push_back( std::move( layer ) );
  }
  return result;
}

static void streamLevels( xivps3::dat::GameData& data, unsigned preferredLanguage )
{
  Ps3Excel::Header header( readAsset( data, "exd/TerritoryType.exh" ) );
  unsigned language = preferredLanguage;
  if( std::find( header.languages.begin(), header.languages.end(), language ) == header.languages.end() )
    language = std::find( header.languages.begin(), header.languages.end(), 0u ) != header.languages.end() ? 0u : header.languages.front();
  size_t count = 0, errors = 0, supportedSgb = 0, unsupportedSgb = 0;
  std::unordered_set< std::string > inspectedSgb;
  for( const auto& page : header.pages )
  {
    const auto path = "exd/TerritoryType_" + std::to_string( page.start ) + languageSuffix( language ) + ".exd";
    const auto bytes = readAsset( data, path );
    Ps3Excel::Binary::rows( header, bytes, [&]( const Ps3Excel::Binary::Row& row ) {
      const auto* lvb = row.fields.size() > 1 ? std::get_if< std::string >( &row.fields[ 1 ] ) : nullptr;
      if( !lvb || lvb->empty() ) return;
      const auto asset = "bg/" + *lvb + ".lvb";
      try
      {
        auto result = inspectLvb( readAsset( data, asset ) );
        result[ "territory_type_id" ] = row.id;
        result[ "lvb_path" ] = asset;
        result[ "lgb_files" ] = Json::array();
        result[ "sgb_files" ] = Json::array();
        for( const auto& lgbPath : result[ "lgb_paths" ] )
        {
          auto lgb = inspectLgb( readAsset( data, lgbPath.get< std::string >() ) );
          lgb[ "path" ] = lgbPath;
          for( const auto& group : lgb[ "groups" ] )
            for( const auto& entry : group[ "entries" ] )
              if( entry.contains( "sgb_path" ) )
              {
                const auto sgbPath = entry[ "sgb_path" ].get< std::string >();
                if( !inspectedSgb.insert( sgbPath ).second ) continue;
                try
                {
                  auto timelines = sharedGroupTimelines( readAsset( data, sgbPath ) );
                  timelines[ "path" ] = sgbPath;
                  result[ "sgb_files" ].push_back( std::move( timelines ) );
                  ++supportedSgb;
                }
                catch( const std::exception& ) { ++unsupportedSgb; }
              }
          result[ "lgb_files" ].push_back( std::move( lgb ) );
        }
        std::cout << result.dump( -1, ' ', false, Json::error_handler_t::replace ) << '\n';
        ++count;
      }
      catch( const std::exception& e )
      {
        Json error = { { "error", true }, { "territory_type_id", row.id }, { "lvb_path", asset }, { "message", e.what() } };
        std::cout << error.dump() << '\n';
        ++errors;
      }
    } );
  }
  std::cerr << count << " LVB files streamed, " << errors << " errors; " << supportedSgb
            << " timeline SGB profiles, " << unsupportedSgb << " other SGB profiles\n";
  if( errors ) throw std::runtime_error( "Incomplete LVB stream" );
}

static void streamExcel( xivps3::dat::GameData& data, unsigned preferredLanguage )
{
  auto root = readAsset( data, "exd/root.exl" );
  std::istringstream input( std::string( root.begin(), root.end() ) );
  std::string line;
  std::getline( input, line );
  size_t sheets = 0, rows = 0, errors = 0;
  while( std::getline( input, line ) )
  {
    if( !line.empty() && line.back() == '\r' ) line.pop_back();
    const auto comma = line.find( ',' );
    if( line.empty() ) continue;
    if( comma == std::string::npos ) throw std::runtime_error( "Malformed root.exl" );
    const auto name = line.substr( 0, comma );
    ++sheets;
    try
    {
      Ps3Excel::Header header( readAsset( data, "exd/" + name + ".exh" ) );
      unsigned language = preferredLanguage;
      if( std::find( header.languages.begin(), header.languages.end(), language ) == header.languages.end() )
      {
        if( std::find( header.languages.begin(), header.languages.end(), 0u ) != header.languages.end() ) language = 0;
        else if( !header.languages.empty() ) language = header.languages.front();
        else throw std::runtime_error( "Sheet declares no language" );
      }
      std::unordered_map< uint32_t, size_t > ordinals;
      for( const auto& page : header.pages )
      {
        const auto path = "exd/" + name + "_" + std::to_string( page.start ) + languageSuffix( language ) + ".exd";
        const auto bytes = readAsset( data, path );
        Ps3Excel::Binary::rows( header, bytes, [&]( const Ps3Excel::Binary::Row& row ) {
          Json values = Json::array();
          for( const auto& cell : row.fields ) values.push_back( compactCell( cell ) );
          Json record = { { "s", name }, { "l", language }, { "i", row.id },
                          { "o", ordinals[ row.id ]++ }, { "k", row.subkeys }, { "v", std::move( values ) } };
          // Replace malformed UTF-8 for searchable presentation while the regular
          // dump command remains available when lossless string bytes are needed.
          std::cout << record.dump( -1, ' ', false, Json::error_handler_t::replace ) << '\n';
          ++rows;
        } );
      }
    }
    catch( const std::exception& e )
    {
      ++errors;
      Json error = { { "error", true }, { "sheet", name }, { "message", e.what() } };
      std::cout << error.dump() << '\n';
    }
  }
  std::cerr << sheets << " sheets, " << rows << " streamed rows, " << errors << " errors\n";
  if( errors ) throw std::runtime_error( "Incomplete EXD stream" );
}

static void searchExcel( xivps3::dat::GameData& data, const std::string& query, const fs::path& output,
                         unsigned preferredLanguage, size_t limit, const SemanticLabels& labels )
{
  bool numeric = false;
  uint64_t number = 0;
  std::string text = query;
  if( text.rfind( "id:", 0 ) == 0 )
  {
    text.erase( 0, 3 );
    size_t consumed = 0;
    number = std::stoull( text, &consumed, 0 );
    if( consumed != text.size() ) throw std::runtime_error( "Invalid numeric ID query: " + query );
    numeric = true;
  }
  const auto folded = lowerAscii( text );
  auto root = readAsset( data, "exd/root.exl" );
  std::istringstream input( std::string( root.begin(), root.end() ) );
  std::string line;
  std::getline( input, line );
  Json result = { { "query", query }, { "mode", numeric ? "id" : "text" },
                  { "preferred_language", preferredLanguage }, { "result_limit", limit },
                  { "matches", Json::array() }, { "schema_matches", Json::array() },
                  { "errors", Json::array() } };
  size_t sheets = 0, rows = 0, matches = 0;
  while( std::getline( input, line ) )
  {
    if( !line.empty() && line.back() == '\r' ) line.pop_back();
    const auto comma = line.find( ',' );
    if( line.empty() ) continue;
    if( comma == std::string::npos ) throw std::runtime_error( "Malformed root.exl" );
    const auto name = line.substr( 0, comma );
    ++sheets;
    try
    {
      Ps3Excel::Header header( readAsset( data, "exd/" + name + ".exh" ) );
      unsigned language = preferredLanguage;
      if( std::find( header.languages.begin(), header.languages.end(), language ) == header.languages.end() )
      {
        if( std::find( header.languages.begin(), header.languages.end(), 0u ) != header.languages.end() ) language = 0;
        else if( !header.languages.empty() ) language = header.languages.front();
        else throw std::runtime_error( "Sheet declares no language" );
      }
      if( !numeric )
      {
        for( size_t column = 0; column < header.columns.size(); ++column )
        {
          const auto label = fieldLabel( labels, name, column );
          if( lowerAscii( label.name ).find( folded ) != std::string::npos )
            result[ "schema_matches" ].push_back( { { "sheet", name }, { "column", column },
              { "field", label.name }, { "field_confidence", label.confidence } } );
        }
      }
      for( const auto& page : header.pages )
      {
        const auto path = "exd/" + name + "_" + std::to_string( page.start ) + languageSuffix( language ) + ".exd";
        const auto bytes = readAsset( data, path );
        Ps3Excel::Binary::rows( header, bytes, [&]( const Ps3Excel::Binary::Row& row ) {
          ++rows;
          Json found = Json::array();
          if( numeric && row.id == number ) found.push_back( { { "kind", "main_key" }, { "value", row.id } } );
          if( numeric )
            for( size_t key = 0; key < row.subkeys.size(); ++key )
              if( row.subkeys[ key ] == number ) found.push_back( {
                { "kind", "subkey" }, { "index", key }, { "value", row.subkeys[ key ] } } );
          for( size_t column = 0; column < row.fields.size(); ++column )
          {
            bool hit = false;
            if( numeric )
            {
              int64_t signedValue = 0;
              uint64_t unsignedValue = 0;
              bool isSigned = false;
              if( integralValue( row.fields[ column ], signedValue, unsignedValue, isSigned ) )
                hit = isSigned ? signedValue >= 0 && static_cast< uint64_t >( signedValue ) == number
                               : unsignedValue == number;
            }
            else if( const auto* value = std::get_if< std::string >( &row.fields[ column ] ) )
              hit = lowerAscii( *value ).find( folded ) != std::string::npos;
            if( hit )
            {
              const auto label = fieldLabel( labels, name, column );
              found.push_back( { { "kind", numeric ? "cell_value" : "text" },
                { "column", column }, { "field", label.name }, { "field_confidence", label.confidence },
                { "type", Ps3Excel::typeName( header.columns[ column ].type ) },
                { "offset", header.columns[ column ].offset }, { "value", Ps3Excel::jsonCell( row.fields[ column ] ) } } );
            }
          }
          if( found.empty() ) return;
          ++matches;
          if( result[ "matches" ].size() < limit ) result[ "matches" ].push_back( {
            { "sheet", name }, { "language", language }, { "id", row.id },
            { "subkeys", row.subkeys }, { "hits", std::move( found ) } } );
        } );
      }
    }
    catch( const std::exception& e )
    {
      result[ "errors" ].push_back( { { "sheet", name }, { "error", e.what() } } );
    }
  }
  result[ "scanned_sheets" ] = sheets;
  result[ "scanned_rows" ] = rows;
  result[ "match_count" ] = matches;
  result[ "returned_matches" ] = result[ "matches" ].size();
  result[ "truncated" ] = matches > limit;
  saveJson( output, result );
  std::cerr << sheets << " sheets, " << rows << " rows, " << matches << " matching rows, "
            << result[ "errors" ].size() << " errors\n";
  if( !result[ "errors" ].empty() ) throw std::runtime_error( "Incomplete EXD search; see output errors" );
}

static void scanExcel( xivps3::dat::GameData& data, const fs::path& output, bool library = false )
{
  auto root = readAsset( data, "exd/root.exl" );
  std::istringstream input( std::string( root.begin(), root.end() ) );
  std::string line;
  std::getline( input, line );
  Json report = { { "decoder", library ? "xivdatps3::Exd (ToolkitPs3 path)" : "shared byte decoder" },
                  { "sheets", Json::array() } };
  size_t errors = 0, rows = 0, pages = 0;
  while( std::getline( input, line ) )
  {
    if( !line.empty() && line.back() == '\r' ) line.pop_back();
    auto comma = line.find( ',' );
    if( line.empty() ) continue;
    if( comma == std::string::npos ) throw std::runtime_error( "Malformed root.exl" );
    auto name = line.substr( 0, comma );
    Json sheet = { { "name", name }, { "root_id", line.substr( comma + 1 ) } };
    try
    {
      auto bytes = readAsset( data, "exd/" + name + ".exh" );
      Ps3Excel::Header header( bytes );
      sheet[ "schema" ] = header.schema();
      sheet[ "validated_pages" ] = Json::array();
      for( auto language : header.languages )
        for( const auto& page : header.pages )
        {
          auto path = "exd/" + name + "_" + std::to_string( page.start ) + languageSuffix( language ) + ".exd";
          Json entry = { { "path", path } };
          try
          {
            size_t count = 0;
            if( library )
            {
              std::shared_ptr< xivps3::dat::File > pageFile = data.getFile( path );
              xivps3::exd::Exd sheet( std::make_shared< xivps3::exd::Exh >( bytes ), { pageFile } );
              for( auto id : sheet.get_ids() )
                for( size_t ordinal = 0; ordinal < sheet.get_subrow_count( id ); ++ordinal )
                {
                  const auto fields = sheet.get_row( id, static_cast< uint32_t >( ordinal ) );
                  if( fields.size() != header.columns.size() ) throw std::runtime_error( "Library column count mismatch" );
                  if( sheet.get_subrow_keys( id, static_cast< uint32_t >( ordinal ) ).size() != header.keyCount - 1 )
                    throw std::runtime_error( "Library key count mismatch" );
                  ++count;
                }
            }
            else Ps3Excel::rows( header, readAsset( data, path ), [&]( const Json& ) { ++count; } );
            entry[ "decoded_rows" ] = count;
            rows += count; ++pages;
          }
          catch( const std::exception& e ) { entry[ "error" ] = e.what(); ++errors; }
          sheet[ "validated_pages" ].push_back( std::move( entry ) );
        }
    }
    catch( const std::exception& e ) { sheet[ "error" ] = e.what(); ++errors; }
    report[ "sheets" ].push_back( std::move( sheet ) );
  }
  report[ "decoded_rows" ] = rows;
  report[ "validated_pages" ] = pages;
  report[ "error_count" ] = errors;
  saveJson( output, report );
  std::cerr << report[ "sheets" ].size() << " sheets, " << pages << " pages, " << rows << " rows, " << errors << " errors\n";
  if( errors ) throw std::runtime_error( "Incomplete EXD scan; see output errors" );
}

int main( int argc, char** argv )
{
  try
  {
    if( argc == 4 && std::string( argv[ 1 ] ) == "inventory" )
      inventory( argv[ 2 ], argv[ 3 ] );
    else if( argc == 6 && std::string( argv[ 1 ] ) == "extract-hash" )
    {
      fs::path indexPath = argv[ 2 ];
      if( !fs::is_regular_file( indexPath ) ) throw std::runtime_error( "Index does not exist: " + indexPath.string() );
      xivps3::dat::Index index( indexPath );
      auto dir = std::stoull( argv[ 3 ], nullptr, 16 );
      auto name = std::stoull( argv[ 4 ], nullptr, 16 );
      if( dir > UINT32_MAX || name > UINT32_MAX ) throw std::runtime_error( "Hash exceeds 32 bits" );
      auto entry = index.getHashTableEntry( static_cast< uint32_t >( dir ), static_cast< uint32_t >( name ) );
      auto datPath = indexPath;
      datPath.replace_extension( ".dat" + std::to_string( entry.datNum ) );
      xivps3::dat::Dat dat( datPath, entry.datNum );
      exportAsset( *dat.getFile( entry.datOffset ), argv[ 5 ] );
    }
    else if( argc == 5 && std::string( argv[ 1 ] ) == "sgb-timelines" )
    {
      xivps3::dat::GameData data( argv[ 2 ] );
      auto out = sharedGroupTimelines( readAsset( data, argv[ 3 ] ) );
      out[ "asset" ] = argv[ 3 ];
      saveJson( argv[ 4 ], out );
    }
    else if( argc == 4 && ( std::string( argv[ 1 ] ) == "exd-scan" || std::string( argv[ 1 ] ) == "exd-library-scan" ) )
    {
      xivps3::dat::GameData data( argv[ 2 ] );
      scanExcel( data, argv[ 3 ], std::string( argv[ 1 ] ) == "exd-library-scan" );
    }
    else if( ( argc == 5 && std::string( argv[ 1 ] ) == "schema" ) ||
             ( argc == 6 && std::string( argv[ 1 ] ) == "dump" ) )
    {
      xivps3::dat::GameData data( argv[ 2 ] );
      saveJson( argv[ 4 ], inspectSheet( data, argv[ 3 ], argc == 6,
                                       argc == 6 ? static_cast< unsigned >( std::stoul( argv[ 5 ] ) ) : 0 ) );
    }
    else if( argc == 4 && std::string( argv[ 1 ] ) == "exd-stream" )
    {
      xivps3::dat::GameData data( argv[ 2 ] );
      streamExcel( data, static_cast< unsigned >( std::stoul( argv[ 3 ] ) ) );
    }
    else if( argc == 4 && std::string( argv[ 1 ] ) == "level-stream" )
    {
      xivps3::dat::GameData data( argv[ 2 ] );
      streamLevels( data, static_cast< unsigned >( std::stoul( argv[ 3 ] ) ) );
    }
    else if( argc >= 5 && argc <= 8 && std::string( argv[ 1 ] ) == "exd-search" )
    {
      xivps3::dat::GameData data( argv[ 2 ] );
      const auto language = argc >= 6 ? static_cast< unsigned >( std::stoul( argv[ 5 ] ) ) : 2u;
      const auto limit = argc >= 7 ? static_cast< size_t >( std::stoull( argv[ 6 ] ) ) : 500u;
      const auto labels = argc >= 8 ? loadSemanticLabels( argv[ 7 ] ) : SemanticLabels{};
      searchExcel( data, argv[ 3 ], argv[ 4 ], language, limit, labels );
    }
    else if( argc == 5 && std::string( argv[ 1 ] ) == "extract" )
    {
      xivps3::dat::GameData data( argv[ 2 ] );
      auto file = data.getFile( argv[ 3 ] );
      exportAsset( *file, argv[ 4 ] );
    }
    else
    {
      std::cerr << "Usage:\n  ps3_data_inspector inventory <game-or-sqpack-root> <output.json>\n"
                << "  ps3_data_inspector extract <sqpack-root> <asset/path> <output-file>\n"
                << "  ps3_data_inspector extract-hash <file.index> <directory-hash-hex> <filename-hash-hex> <output-file>\n"
                << "  ps3_data_inspector exd-library-scan <sqpack-root> <output.json>\n"
                << "  ps3_data_inspector schema <sqpack-root> <sheet> <output.json>\n"
                << "  ps3_data_inspector dump <sqpack-root> <sheet> <output.json> <language-id>\n"
                << "  ps3_data_inspector exd-scan <sqpack-root> <output.json>\n"
                << "  ps3_data_inspector exd-search <sqpack-root> <text|id:NUMBER> <output.json> [language-id] [limit] [semantic-schema.json]\n"
                << "  ps3_data_inspector exd-stream <sqpack-root> <language-id>\n"
                << "  ps3_data_inspector level-stream <sqpack-root> <language-id>\n"
                << "  ps3_data_inspector sgb-timelines <sqpack-root> <asset/path.sgb> <output.json>\n";
      return 2;
    }
    return 0;
  }
  catch( const std::exception& e ) { std::cerr << e.what() << '\n'; return 1; }
}
