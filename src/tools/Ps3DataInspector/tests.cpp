#include "Excel.h"
#include <Dat.h>
#include <File.h>
#include <Index.h>
#include <Exd.h>
#include <Exh.h>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>

using namespace Ps3Excel;

static void check( bool ok, const char* message )
{
  if( !ok ) throw std::runtime_error( message );
}

static void put( Bytes& b, size_t p, uint64_t value, size_t n )
{
  require( b, p, n );
  for( size_t i = 0; i < n; ++i ) b[ p + n - 1 - i ] = static_cast< char >( value >> ( i * 8 ) );
}

static void text( Bytes& b, size_t p, const char* s ) { std::memcpy( b.data() + p, s, std::strlen( s ) ); }

template< typename F > static void rejects( F f )
{
  try { f(); } catch( const std::runtime_error& ) { return; } catch( const std::out_of_range& ) { return; }
  throw std::runtime_error( "Expected parse rejection" );
}

static void excelTests()
{
  Bytes h( 58, 0 ); text( h, 0, "EXHF" );
  put( h, 4, 3, 2 ); put( h, 6, 8, 2 ); put( h, 8, 4, 2 );
  put( h, 10, 1, 2 ); put( h, 12, 1, 2 ); put( h, 16, 2, 2 ); put( h, 20, 1, 4 );
  put( h, 32, 0, 2 ); put( h, 34, 0, 2 );
  put( h, 36, 4, 2 ); put( h, 38, 4, 2 );
  put( h, 40, 25, 2 ); put( h, 42, 7, 2 );
  put( h, 44, 32, 2 ); put( h, 46, 7, 2 );
  put( h, 48, 100, 4 ); put( h, 52, 1, 4 ); h[ 56 ] = 2;
  Header header( h );
  check( header.languages.front() == 2, "Language must be byte-sized" );
  check( header.columns.size() == 4, "Packed booleans must not collapse by offset" );
  Bytes b( 74, 0 ); text( b, 0, "EXDF" ); put( b, 4, 2, 2 ); put( b, 8, 8, 4 );
  put( b, 32, 100, 4 ); put( b, 36, 40, 4 ); put( b, 40, 28, 4 ); put( b, 44, 2, 2 );
  put( b, 46, 42, 2 ); put( b, 48, 0, 4 ); put( b, 52, 0xFFFE, 2 ); b[ 55 ] = static_cast< char >( 0x81 );
  put( b, 56, 513, 2 ); put( b, 58, 4, 4 ); put( b, 62, 1234, 2 ); b[ 65 ] = 1;
  text( b, 66, "abc" ); text( b, 70, "def" );
  std::vector< Json > decoded;
  rows( header, b, [&]( const Json& row ) { decoded.push_back( row ); } );
  check( decoded.size() == 2, "Expected two subrows" );
  check( decoded[ 0 ][ "fields" ][ 0 ][ "text" ] == "abc", "Shared string pool (first subrow)" );
  check( decoded[ 1 ][ "fields" ][ 0 ][ "text" ] == "def", "Shared string pool (second subrow)" );
  check( decoded[ 1 ][ "subkeys" ][ 0 ] == 513, "Subkeys are IDs, not ordinal indices" );
  check( decoded[ 0 ][ "fields" ][ 1 ] == -2, "BE signed integer" );
  check( decoded[ 0 ][ "fields" ][ 2 ] == true && decoded[ 0 ][ "fields" ][ 3 ] == true,
         "Packed bool bits 0 and 7" );
  check( decoded[ 1 ][ "fields" ][ 3 ] == false, "Packed bool false" );
  // Exercise the exact library and typed-row paths used by ToolkitPs3.
  auto legacyHeader = std::make_shared< xivps3::exd::Exh >( h );
  auto page = std::make_shared< xivps3::dat::File >();
  page->access_data_sections().push_back( b );
  xivps3::exd::Exd sheet( legacyHeader, { page } );
  check( legacyHeader->get_exh_members().size() == 4, "Library keeps repeated column offsets" );
  check( static_cast< unsigned >( legacyHeader->get_languages().front() ) == 2, "Library language byte" );
  check( sheet.get_subrow_count( 100 ) == 2, "Library subrow count" );
  check( sheet.get_subrow_keys( 100, 1 ) == std::vector< uint16_t >{ 513 }, "Library subkey ID" );
  check( std::get< std::string >( sheet.get_row( 100, 1 )[ 0 ] ) == "def", "Library shared subrow string" );
  check( sheet.get_ids() == std::vector< uint32_t >{ 100 }, "ID enumeration without decoding every row" );
  check( sheet.get_rows().at( 100 ).size() == 4, "First get_rows" );
  check( sheet.get_rows().at( 100 ).size() == 4 && sheet.get_row( 100 ).size() == 4,
         "Repeated reads must not append fields" );
  struct TypedRow
  {
    Excel::Ps3::StringOffset name;
    int16_t number;
    uint8_t padding;
    // Same declaration order convention as the legacy Excel::Ps3 structs.
    uint8_t bit7 : 1;
    uint8_t unused : 6;
    uint8_t bit0 : 1;
  };
  static_assert( sizeof( TypedRow ) == 8 );
  auto typed = sheet.get_row< TypedRow >( 100, 1 );
  check( typed->getString( typed->data().name ) == "def" && typed->data().number == 1234,
         "Typed row ordinal and endian conversion" );
  check( typed->data().bit0 && !typed->data().bit7, "Typed packed flags normalized to legacy host declaration order" );
  check( sheet.get_row< TypedRow >( 100 )->data().number == -2, "Typed signed value" );
  rejects( [&] { sheet.get_row( 100, 2 ); } );
  rejects( [&] { sheet.get_row< TypedRow >( 100, 513 ); } ); // key ID is not an ordinal
  rejects( [&] { sheet.get_row< uint32_t >( 100 ); } );
  auto singleHeader = h; put( singleHeader, 16, 1, 2 );
  Bytes single( 58, 0 ); text( single, 0, "EXDF" ); put( single, 8, 8, 4 );
  put( single, 32, 101, 4 ); put( single, 36, 40, 4 ); put( single, 40, 12, 4 ); put( single, 44, 1, 2 );
  put( single, 50, 0xFFFE, 2 ); single[ 53 ] = static_cast< char >( 0x80 ); text( single, 54, "abc" );
  auto singlePage = std::make_shared< xivps3::dat::File >(); singlePage->access_data_sections().push_back( single );
  xivps3::exd::Exd singleSheet( std::make_shared< xivps3::exd::Exh >( singleHeader ), { singlePage } );
  check( singleSheet.get_subrow_keys( 101, 0 ).empty(), "Single-key rows have no subkey prefix" );
  auto singleTyped = singleSheet.get_row< TypedRow >( 101 );
  check( singleTyped->getString( singleTyped->data().name ) == "abc" && singleTyped->data().number == -2 &&
         singleTyped->data().bit7 && !singleTyped->data().bit0, "Single-key typed string and flags" );

  auto fourKeysHeader = h; put( fourKeysHeader, 16, 4, 2 );
  Bytes fourKeys( 82, 0 ); text( fourKeys, 0, "EXDF" ); put( fourKeys, 8, 8, 4 );
  put( fourKeys, 32, 102, 4 ); put( fourKeys, 36, 40, 4 ); put( fourKeys, 40, 36, 4 ); put( fourKeys, 44, 2, 2 );
  put( fourKeys, 46, 42, 2 ); put( fourKeys, 48, 513, 2 ); put( fourKeys, 50, 65535, 2 );
  put( fourKeys, 60, 7, 2 ); put( fourKeys, 62, 9, 2 ); put( fourKeys, 64, 11, 2 );
  put( fourKeys, 66, 4, 4 ); text( fourKeys, 74, "abc" ); text( fourKeys, 78, "def" );
  auto fourPage = std::make_shared< xivps3::dat::File >(); fourPage->access_data_sections().push_back( fourKeys );
  xivps3::exd::Exd fourSheet( std::make_shared< xivps3::exd::Exh >( fourKeysHeader ), { fourPage } );
  check( fourSheet.get_subrow_keys( 102, 0 ) == std::vector< uint16_t >{ 42, 513, 65535 }, "All three subkey IDs" );
  check( std::get< std::string >( fourSheet.get_row( 102, 1 )[ 0 ] ) == "def", "Four-key shared string pool" );

  auto broken = b; broken.pop_back();
  rejects( [&] { rows( header, broken, []( const Json& ) {} ); } );
  broken = b; broken[ 73 ] = 'x';
  rejects( [&] { rows( header, broken, []( const Json& ) {} ); } );
  broken = b; put( broken, 48, 0xFFFFFFFF, 4 );
  rejects( [&] { rows( header, broken, []( const Json& ) {} ); } );
  broken = h; put( broken, 4, 2, 2 ); rejects( [&] { Header unsupported( broken ); } );
  rejects( [&] { width( 12 ); } );
  Bytes number( 8, static_cast< char >( 0xFF ) );
  check( cell( number, { 10, 0 }, 0, 8, 8 ) == -1, "Signed 64-bit" );
  check( cell( number, { 11, 0 }, 0, 8, 8 ).get< uint64_t >() == UINT64_MAX, "Unsigned 64-bit" );
  put( number, 0, 0x3F800000, 4 );
  check( cell( number, { 9, 0 }, 0, 8, 8 ) == 1.0, "BE float32" );
  put( number, 0, 0x7FC00000, 4 );
  check( cell( number, { 9, 0 }, 0, 8, 8 )[ "f32_bits" ] == 0x7FC00000, "Nonfinite float bits" );
  put( number, 0, 0x3C00, 2 );
  check( cell( number, { 8, 0 }, 0, 8, 8 )[ "f16_bits" ] == 0x3C00, "F16 bits" );
  check( std::get< xivps3::exd::binary::HalfBits >( xivps3::exd::binary::cell( number, { 8, 0 }, 0, 8, 8, 8 ) ).bits == 0x3C00,
         "Library F16 raw representation" );

  // The row's subrow count is 16 bits, not the low byte used by the old reader.
  header.fixedSize = 1; header.columns = { { 3, 0 } };
  Bytes many( 46 + 257 * 3, 0 ); text( many, 0, "EXDF" ); put( many, 8, 8, 4 );
  put( many, 32, 100, 4 ); put( many, 36, 40, 4 ); put( many, 40, 257 * 3, 4 ); put( many, 44, 257, 2 );
  size_t count = 0; rows( header, many, [&]( const Json& ) { ++count; } );
  check( count == 257, "16-bit subrow count" );
  auto manyHeader = h;
  put( manyHeader, 6, 1, 2 ); put( manyHeader, 8, 1, 2 );
  // Remove unused columns and move the page/language descriptors.
  manyHeader.resize( 46 ); put( manyHeader, 32, 3, 2 ); put( manyHeader, 34, 0, 2 );
  put( manyHeader, 36, 100, 4 ); put( manyHeader, 40, 1, 4 ); manyHeader[ 44 ] = 2;
  auto manyPage = std::make_shared< xivps3::dat::File >();
  manyPage->access_data_sections().push_back( many );
  xivps3::exd::Exd largeSheet( std::make_shared< xivps3::exd::Exh >( manyHeader ), { manyPage } );
  check( largeSheet.get_subrow_count( 100 ) == 257 && largeSheet.get_row( 100, 256 ).size() == 1,
         "Library reads all 16 subrow-count bits" );

  broken = b; put( broken, 36, 32, 4 );
  auto badPage = std::make_shared< xivps3::dat::File >(); badPage->access_data_sections().push_back( broken );
  rejects( [&] { xivps3::exd::Exd invalid( legacyHeader, { badPage } ); } );
  broken = b; put( broken, 40, UINT32_MAX, 4 ); badPage->access_data_sections().front() = broken;
  rejects( [&] { xivps3::exd::Exd invalid( legacyHeader, { badPage } ); } );
  rejects( [&] { xivps3::exd::Exd duplicate( legacyHeader, { page, page } ); } );
}

static void sdatTests()
{
  namespace fs = std::filesystem;
  const auto plainPath = fs::temp_directory_path() / "sapphire-ps3-sdat-test.dat0";
  const auto sdatPath = fs::path( plainPath.string() + ".sdat" );
  struct Cleanup
  {
    fs::path plain;
    fs::path sdat;
    ~Cleanup()
    {
      std::error_code error;
      fs::remove( plain, error );
      fs::remove( sdat, error );
    }
  } cleanup{ plainPath, sdatPath };

  Bytes logical( 0x8100 );
  for( size_t i = 0; i < logical.size(); ++i ) logical[ i ] = static_cast< char >( i * 37 );
  std::memcpy( logical.data(), "SqPack\0\0", 8 );

  Bytes physical( 0x100, 0 );
  std::memcpy( physical.data(), "NPD\0", 4 );
  put( physical, 4, 4, 4 );
  put( physical, 0x80, 0x8100003C, 4 );
  put( physical, 0x84, 0x4000, 4 );
  put( physical, 0x88, logical.size(), 8 );
  size_t logicalOffset = 0;
  while( logicalOffset < logical.size() )
  {
    physical.insert( physical.end(), 0x20, static_cast< char >( 0xCC ) );
    const size_t length = std::min< size_t >( 0x4000, logical.size() - logicalOffset );
    physical.insert( physical.end(), logical.begin() + logicalOffset, logical.begin() + logicalOffset + length );
    logicalOffset += length;
  }
  { std::ofstream out( sdatPath, std::ios::binary ); out.write( physical.data(), physical.size() ); }

  class ProbeSqPack : public xivps3::dat::SqPack
  {
  public:
    explicit ProbeSqPack( const fs::path& path ) : SqPack( path ) {}
    bool isSdat() const { return m_handle.isSdat(); }
    Bytes readAt( size_t offset, size_t size )
    {
      Bytes result( size );
      m_handle.clear();
      m_handle.seekg( static_cast< std::streamoff >( offset ) );
      m_handle.read( result.data(), static_cast< std::streamsize >( result.size() ) );
      check( m_handle.gcount() == static_cast< std::streamsize >( result.size() ), "Short logical SDAT read" );
      return result;
    }
  };

  ProbeSqPack fallback( plainPath );
  check( fallback.isSdat(), "Missing DAT must fall back to DAT.sdat" );
  check( fallback.readAt( 0x3FF0, 0x40 ) == Bytes( logical.begin() + 0x3FF0, logical.begin() + 0x4030 ),
         "Logical SDAT reads must cross metadata boundaries" );

  { std::ofstream out( plainPath, std::ios::binary ); out.write( logical.data(), logical.size() ); }
  ProbeSqPack preferredSdat( plainPath );
  check( preferredSdat.isSdat(), "DAT.sdat must take precedence over a plain DAT" );

  std::error_code removeError;
  fs::remove( sdatPath, removeError );
  check( !removeError, "Failed to remove synthetic SDAT" );
  ProbeSqPack plain( plainPath );
  check( !plain.isSdat(), "Plain DAT must be used when DAT.sdat is absent" );
  check( plain.readAt( 0x8000, 0x40 ) == Bytes( logical.begin() + 0x8000, logical.begin() + 0x8040 ),
         "Plain DAT reads must remain unchanged" );
}

static void offsetTests()
{
  namespace fs = std::filesystem;
  const auto path = fs::temp_directory_path() / "sapphire-ps3-inspector-test.index";
  struct Cleanup { fs::path path; ~Cleanup() { std::error_code ec; fs::remove( path, ec ); } } cleanup{ path };
  Bytes b( 0x810, 0 ); text( b, 0, "SqPack" );
  put( b, 0x408, 0x800, 4 ); put( b, 0x40C, 16, 4 ); put( b, 0x450, 1, 4 );
  put( b, 0x800, 0x12345678, 4 ); put( b, 0x804, 0x9ABCDEF0, 4 );
  put( b, 0x808, 0x2000001, 4 );
  { std::ofstream out( path, std::ios::binary ); out.write( b.data(), b.size() ); }
  xivps3::dat::Index index( path );
  const auto& entry = index.getHashTableEntry( 0x12345678, 0x9ABCDEF0 );
  check( entry.dirHash == 0x12345678 && entry.filenameHash == 0x9ABCDEF0, "Inventory hash fields populated" );
  check( entry.datOffset == UINT64_C( 0x100000080 ), "PS3 index offset beyond 4 GiB" );
  static_assert( sizeof( entry.datOffset ) == 8 );
}

int main()
{
  try { excelTests(); sdatTests(); offsetTests(); std::cout << "PS3 Excel/index/SDAT tests passed\n"; return 0; }
  catch( const std::exception& e ) { std::cerr << e.what() << '\n'; return 1; }
}
