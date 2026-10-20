#include "DataGraphBrowser.h"

#include <sqlite3.h>
#include <nlohmann/json.hpp>
#include <algorithm>
#include <cctype>
#include <climits>
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <unordered_set>

namespace
{
  using Json = nlohmann::json;

  class Statement
  {
  public:
    Statement( sqlite3* db, const char* sql ) : m_db( db )
    {
      if( sqlite3_prepare_v2( db, sql, -1, &m_stmt, nullptr ) != SQLITE_OK )
        throw std::runtime_error( sqlite3_errmsg( db ) );
    }
    ~Statement() { sqlite3_finalize( m_stmt ); }
    sqlite3_stmt* get() const { return m_stmt; }
    void text( int index, const std::string& value )
    {
      if( sqlite3_bind_text( m_stmt, index, value.c_str(), -1, SQLITE_TRANSIENT ) != SQLITE_OK )
        throw std::runtime_error( sqlite3_errmsg( m_db ) );
    }
    void integer( int index, int64_t value )
    {
      if( sqlite3_bind_int64( m_stmt, index, value ) != SQLITE_OK )
        throw std::runtime_error( sqlite3_errmsg( m_db ) );
    }
    bool row()
    {
      const auto result = sqlite3_step( m_stmt );
      if( result == SQLITE_ROW ) return true;
      if( result != SQLITE_DONE ) throw std::runtime_error( sqlite3_errmsg( m_db ) );
      return false;
    }
    int64_t i64( int column ) const { return sqlite3_column_int64( m_stmt, column ); }
    int integer( int column ) const { return sqlite3_column_int( m_stmt, column ); }
    std::string string( int column ) const
    {
      const auto* value = sqlite3_column_text( m_stmt, column );
      return value ? reinterpret_cast< const char* >( value ) : std::string{};
    }
  private:
    sqlite3* m_db{};
    sqlite3_stmt* m_stmt{};
  };

  std::string formatNumber( int64_t value )
  {
    std::ostringstream out;
    out << value;
    if( value >= 10 ) out << " (0x" << std::uppercase << std::hex << value << ')';
    return out.str();
  }

  std::string formatRowLabel( const std::string& sheet, int64_t id, int ordinal, bool alwaysOrdinal = false )
  {
    auto label = sheet + ":" + formatNumber( id );
    if( ordinal || alwaysOrdinal ) label += ":" + formatNumber( ordinal );
    return label;
  }

  std::string formatRowTarget( const std::string& target )
  {
    const auto last = target.rfind( ':' );
    if( last == std::string::npos ) return target;
    const auto previous = target.rfind( ':', last - 1 );
    if( previous == std::string::npos ) return target;
    try
    {
      return formatRowLabel( target.substr( 0, previous ), std::stoll( target.substr( previous + 1, last - previous - 1 ) ),
                             std::stoi( target.substr( last + 1 ) ), true );
    }
    catch( ... ) { return target; }
  }

  bool parseNumber( std::string text, int64_t& value )
  {
    const auto first = text.find_first_not_of( " \t\r\n" );
    if( first == std::string::npos ) return false;
    const auto last = text.find_last_not_of( " \t\r\n" );
    text = text.substr( first, last - first + 1 );
    if( text.size() >= 3 && std::tolower( static_cast< unsigned char >( text[ 0 ] ) ) == 'i' &&
        std::tolower( static_cast< unsigned char >( text[ 1 ] ) ) == 'd' && text[ 2 ] == ':' )
    {
      text.erase( 0, 3 );
      const auto numberFirst = text.find_first_not_of( " \t" );
      if( numberFirst == std::string::npos ) return false;
      text.erase( 0, numberFirst );
    }
    const auto annotation = text.find( " (0x" );
    if( annotation != std::string::npos && text.back() == ')' ) text.resize( annotation );
    int base = 10;
    if( text.size() > 2 && text[ 0 ] == '0' && ( text[ 1 ] == 'x' || text[ 1 ] == 'X' ) )
    {
      base = 16;
      text.erase( 0, 2 );
    }
    if( text.empty() ) return false;
    try
    {
      size_t consumed = 0;
      const auto parsed = std::stoull( text, &consumed, base );
      if( consumed != text.size() || parsed > static_cast< uint64_t >( std::numeric_limits< int64_t >::max() ) ) return false;
      value = static_cast< int64_t >( parsed );
      return true;
    }
    catch( ... ) { return false; }
  }

  int editDistance( const std::string& a, const std::string& b )
  {
    std::vector< int > previous( b.size() + 1 ), current( b.size() + 1 );
    for( size_t j = 0; j <= b.size(); ++j ) previous[ j ] = static_cast< int >( j );
    for( size_t i = 1; i <= a.size(); ++i )
    {
      current[ 0 ] = static_cast< int >( i );
      for( size_t j = 1; j <= b.size(); ++j )
        current[ j ] = std::min( { current[ j - 1 ] + 1, previous[ j ] + 1,
                                  previous[ j - 1 ] + ( a[ i - 1 ] == b[ j - 1 ] ? 0 : 1 ) } );
      previous.swap( current );
    }
    return previous.back();
  }

  ImVec4 confidenceColor( const std::string& confidence )
  {
    if( confidence == "runtime_confirmed" || confidence == "disassembly_confirmed" ) return { 0.2f, 0.9f, 0.35f, 1.0f };
    if( confidence == "source_code_confirmed" ) return { 0.35f, 0.8f, 1.0f, 1.0f };
    if( confidence == "metadata_candidate" || confidence == "format_inferred_candidate" || confidence == "legacy_struct_candidate" || confidence == "structural_candidate" ) return { 0.95f, 0.75f, 0.25f, 1.0f };
    if( confidence == "cross_version_candidate" || confidence == "conditional_candidate" || confidence == "content_workflow_candidate" ||
        confidence == "exact_value_candidate" || confidence == "encoded_value_candidate" || confidence == "offset_hypothesis" ) return { 0.9f, 0.5f, 0.25f, 1.0f };
    return { 0.65f, 0.65f, 0.65f, 1.0f };
  }
}

Client::DataGraphBrowser::~DataGraphBrowser()
{
  close();
}

void Client::DataGraphBrowser::setDatabasePath( const std::filesystem::path& path )
{
  if( path == m_path ) return;
  close();
  m_path = path;
  reset();
}

void Client::DataGraphBrowser::close()
{
  if( m_db ) sqlite3_close( m_db );
  m_db = nullptr;
}

bool Client::DataGraphBrowser::open()
{
  if( m_db ) return true;
  if( m_path.empty() ) { m_error = "No graph database path configured."; return false; }
  if( sqlite3_open_v2( m_path.string().c_str(), &m_db, SQLITE_OPEN_READONLY, nullptr ) != SQLITE_OK )
  {
    m_error = m_db ? sqlite3_errmsg( m_db ) : "Could not open SQLite database";
    close();
    return false;
  }
  try
  {
    Statement check( m_db, "SELECT value FROM metadata WHERE key='statistics'" );
    if( !check.row() ) throw std::runtime_error( "Not a PS3 semantic graph database" );
    Statement version( m_db, "SELECT value FROM metadata WHERE key='schema_version'" );
    if( !version.row() || version.string( 0 ) != "5" )
      throw std::runtime_error( "The graph database is outdated; rebuild it with ps3_data_graph.py" );
    Statement schema( m_db, "SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN ('row_data','edge','asset','placement','sgb_timeline','sgb_slot','lua_script','lua_symbol','lua_row_link','lua_source_file','lua_source_reference','lua_source_fts')" );
    if( !schema.row() || schema.integer( 0 ) != 12 )
      throw std::runtime_error( "The graph database is incomplete; rebuild it with ps3_data_graph.py" );
    m_error.clear();
    return true;
  }
  catch( const std::exception& ex )
  {
    m_error = ex.what();
    close();
    return false;
  }
}

void Client::DataGraphBrowser::reset()
{
  m_rows.clear(); m_sources.clear(); m_scripts.clear(); m_rowScripts.clear(); m_cells.clear(); m_outgoing.clear(); m_incoming.clear();
  m_exactCandidates.clear(); m_encodedCandidates.clear(); m_offsetCandidates.clear(); m_consumers.clear();
  m_assetChildren.clear(); m_layerSets.clear(); m_placements.clear(); m_timelines.clear(); m_timelineSlots.clear();
  m_selectedRowPk = 0; m_selectedAsset.clear();
  m_history.clear(); m_historyIndex = static_cast< size_t >( -1 );
  m_selectedSource = {}; m_sourcePreview.clear(); m_selectedLuaPath.clear(); m_luaPreview.clear(); m_hasExcelRequest = false;
  m_error.clear(); m_correction.clear();
}

bool Client::DataGraphBrowser::openRow( const std::string& sheet, uint32_t id, uint32_t ordinal )
{
  if( !open() ) return false;
  try
  {
    Statement row( m_db, "SELECT r.row_pk FROM row_data r JOIN sheet s USING(sheet_id) WHERE s.name=? AND r.main_id=? AND r.ordinal=?" );
    row.text( 1, sheet ); row.integer( 2, id ); row.integer( 3, ordinal );
    if( !row.row() ) return false;
    navigateRow( row.i64( 0 ) );
    return true;
  }
  catch( const std::exception& ex ) { m_error = ex.what(); return false; }
}

bool Client::DataGraphBrowser::openFieldReference( const std::string& sheet, uint32_t id, uint32_t ordinal, int column )
{
  if( !openRow( sheet, id, ordinal ) ) return false;
  try
  {
    Statement links( m_db, "SELECT coalesce(e.target_row,0),e.target_kind,e.target_name FROM edge e JOIN row_data r ON r.row_pk=e.source_row JOIN sheet s ON s.sheet_id=r.sheet_id JOIN field f ON f.field_id=e.source_field WHERE s.name=? AND r.main_id=? AND r.ordinal=? AND f.column_index=?" );
    links.text( 1, sheet ); links.integer( 2, id ); links.integer( 3, ordinal ); links.integer( 4, column );
    std::vector< Link > targets;
    while( links.row() ) targets.push_back( { links.i64( 0 ), links.string( 2 ), {}, {}, {}, links.string( 1 ), links.string( 2 ) } );
    if( targets.size() == 1 )
    {
      if( targets.front().kind == "row" && targets.front().rowPk ) navigateRow( targets.front().rowPk );
      else if( targets.front().kind == "asset" ) navigateAsset( targets.front().target );
    }
    return true;
  }
  catch( const std::exception& ex ) { m_error = ex.what(); return false; }
}

void Client::DataGraphBrowser::searchFor( const std::string& text )
{
  std::snprintf( m_searchBuffer, sizeof( m_searchBuffer ), "%s", text.c_str() );
  search();
}

std::vector< Client::DataGraphBrowser::SemanticField > Client::DataGraphBrowser::semanticFields( const std::string& sheet )
{
  std::vector< SemanticField > fields;
  if( !open() ) return fields;
  try
  {
    Statement query( m_db, "SELECT f.column_index,f.name,f.confidence,f.labels_json,f.references_json FROM field f JOIN sheet s USING(sheet_id) WHERE s.name=? ORDER BY f.column_index" );
    query.text( 1, sheet );
    while( query.row() )
    {
      std::string evidence;
      const auto labels = Json::parse( query.string( 3 ) );
      for( const auto& label : labels )
        if( label.value( "name", "" ) == query.string( 1 ) ) { evidence = label.value( "evidence", "" ); break; }
      std::string references;
      for( const auto& relation : Json::parse( query.string( 4 ) ) )
      {
        if( !references.empty() ) references += "; ";
        if( relation.contains( "targets" ) )
        {
          bool first = true;
          for( const auto& target : relation[ "targets" ] )
          {
            if( !first ) references += " | ";
            references += target.get< std::string >(); first = false;
          }
        }
        else references += "conditional target";
        if( relation.contains( "when" ) )
        {
          const auto& when = relation[ "when" ];
          references += " when " + when.value( "field", "?" ) + "=";
          bool first = true;
          for( const auto& value : when[ "values" ] )
          {
            if( !first ) references += "|";
            references += value.is_number_integer() ? formatNumber( value.get< int64_t >() ) : value.dump(); first = false;
          }
        }
        const auto lookup = relation.value( "lookup", "" );
        if( !lookup.empty() ) references += " (" + lookup + ")";
        if( relation.contains( "source_rows" ) )
        {
          references += " for rows ";
          bool first = true;
          for( const auto& value : relation[ "source_rows" ] )
          {
            if( !first ) references += "|";
            references += value.is_number_integer() ? formatNumber( value.get< int64_t >() ) : value.dump(); first = false;
          }
        }
      }
      fields.push_back( { query.integer( 0 ), query.string( 1 ), query.string( 2 ), std::move( evidence ), std::move( references ) } );
    }
  }
  catch( const std::exception& ex ) { m_error = ex.what(); }
  return fields;
}

bool Client::DataGraphBrowser::takeExcelRequest( ExcelRequest& request )
{
  if( !m_hasExcelRequest ) return false;
  request = m_excelRequest; m_hasExcelRequest = false;
  return true;
}

std::vector< std::string > Client::DataGraphBrowser::queryTerms( const std::string& query )
{
  static const std::unordered_set< std::string > stop = {
    "all", "and", "are", "based", "how", "in", "involved", "is", "of", "on", "the", "to", "what"
  };
  std::vector< std::string > terms;
  for( size_t i = 0; i < query.size(); )
  {
    while( i < query.size() && !std::isalnum( static_cast< unsigned char >( query[ i ] ) ) ) ++i;
    size_t start = i;
    while( i < query.size() && ( std::isalnum( static_cast< unsigned char >( query[ i ] ) ) || query[ i ] == '\'' ) ) ++i;
    if( start == i ) continue;
    std::string word = query.substr( start, i - start );
    std::transform( word.begin(), word.end(), word.begin(), []( unsigned char c ) { return static_cast< char >( std::tolower( c ) ); } );
    if( word.size() < 3 || stop.count( word ) ) continue;
    Statement exact( m_db, "SELECT 1 FROM word WHERE word=?" ); exact.text( 1, word );
    if( !exact.row() )
    {
      std::string best;
      int bestDistance = INT_MAX;
      Statement candidates( m_db, "SELECT word FROM word WHERE substr(word,1,1)=substr(?,1,1) AND length(word) BETWEEN ? AND ? ORDER BY uses DESC LIMIT 10000" );
      candidates.text( 1, word ); candidates.integer( 2, std::max< int >( 1, static_cast< int >( word.size() ) - 2 ) );
      candidates.integer( 3, static_cast< int >( word.size() ) + 2 );
      while( candidates.row() )
      {
        auto candidate = candidates.string( 0 );
        const auto distance = editDistance( word, candidate );
        if( distance < bestDistance ) { bestDistance = distance; best = std::move( candidate ); }
      }
      if( !best.empty() && bestDistance <= std::max< int >( 1, static_cast< int >( word.size() ) / 4 ) )
      {
        if( !m_correction.empty() ) m_correction += ", ";
        m_correction += word + " -> " + best;
        word = best;
      }
    }
    if( std::find( terms.begin(), terms.end(), word ) == terms.end() ) terms.push_back( std::move( word ) );
  }
  return terms;
}

void Client::DataGraphBrowser::search()
{
  m_rows.clear(); m_sources.clear(); m_scripts.clear(); m_error.clear(); m_correction.clear();
  if( !open() ) return;
  try
  {
    std::string query = m_searchBuffer;
    int64_t number = 0;
    const bool numeric = parseNumber( query, number );
    if( numeric )
    {
      Statement rows( m_db, "SELECT r.row_pk,s.name,r.main_id,r.ordinal,coalesce(r.display,''),'main key' FROM row_data r JOIN sheet s USING(sheet_id) WHERE r.main_id=? LIMIT 200" );
      rows.integer( 1, number );
      while( rows.row() ) m_rows.push_back( { rows.i64( 0 ), rows.string( 1 ), rows.i64( 2 ), rows.integer( 3 ), rows.string( 4 ), {}, rows.string( 5 ) } );
      Statement cells( m_db, "SELECT DISTINCT r.row_pk,s.name,r.main_id,r.ordinal,coalesce(r.display,''),f.name FROM number_cell n JOIN row_data r USING(row_pk) JOIN field f USING(field_id) JOIN sheet s ON s.sheet_id=r.sheet_id WHERE n.value=? LIMIT 200" );
      cells.integer( 1, number );
      while( cells.row() ) m_rows.push_back( { cells.i64( 0 ), cells.string( 1 ), cells.i64( 2 ), cells.integer( 3 ), cells.string( 4 ), {}, "value in " + cells.string( 5 ) } );
      Statement source( m_db, "SELECT path,line,context,coalesce(semantic,'numeric literal') FROM source_number WHERE value=? ORDER BY semantic IS NULL,path,line LIMIT 200" );
      source.integer( 1, number );
      while( source.row() ) m_sources.push_back( { source.string( 0 ), source.string( 2 ), source.string( 3 ), source.integer( 1 ) } );
    }
    else
    {
      Statement exactRows( m_db, "SELECT r.row_pk,s.name,r.main_id,r.ordinal,coalesce(r.display,''),f.name FROM text_cell t JOIN row_data r USING(row_pk) JOIN field f USING(field_id) JOIN sheet s USING(sheet_id) WHERE t.value=? LIMIT 200" );
      exactRows.text( 1, query );
      while( exactRows.row() ) m_rows.push_back( { exactRows.i64( 0 ), exactRows.string( 1 ), exactRows.i64( 2 ), exactRows.integer( 3 ), exactRows.string( 4 ), {}, "exact " + exactRows.string( 5 ) } );
      Statement exactScripts( m_db, "SELECT coalesce(link.row_pk,0),CASE WHEN reference.symbol IS NOT NULL THEN source.path ELSE script.display_path END,script.display_path,symbol.symbol,symbol.kind,coalesce(link.confidence,''),symbol.uses,coalesce(reference.line,0),coalesce(reference.context,''),coalesce(source.provenance,'bytecode_only') FROM lua_symbol symbol JOIN lua_script script USING(script_id) LEFT JOIN lua_row_link link USING(script_id,symbol) LEFT JOIN lua_source_file source USING(script_id) LEFT JOIN lua_source_reference reference ON reference.file_id=source.file_id AND reference.symbol=symbol.symbol WHERE symbol.symbol=? ORDER BY source.path,reference.line,script.display_path LIMIT 200" );
      exactScripts.text( 1, query );
      while( exactScripts.row() ) m_scripts.push_back( { exactScripts.i64( 0 ), exactScripts.string( 1 ), exactScripts.string( 2 ), exactScripts.string( 3 ), exactScripts.string( 4 ), exactScripts.string( 5 ), exactScripts.string( 9 ), exactScripts.string( 8 ), exactScripts.integer( 6 ), exactScripts.integer( 7 ) } );
      const auto terms = queryTerms( query );
      if( terms.empty() ) throw std::runtime_error( "Enter searchable words or id:NUMBER" );
      std::ostringstream expression;
      for( size_t i = 0; i < terms.size(); ++i ) { if( i ) expression << " OR "; expression << '"' << terms[ i ] << '"'; }
      Statement rows( m_db, "SELECT r.row_pk,s.name,r.main_id,r.ordinal,coalesce(r.display,''),snippet(row_fts,3,'[',']',' ... ',20) FROM row_fts JOIN row_data r ON r.row_pk=CAST(row_fts.row_pk AS INTEGER) JOIN sheet s USING(sheet_id) WHERE row_fts MATCH ? ORDER BY bm25(row_fts) LIMIT 200" );
      rows.text( 1, expression.str() );
      while( rows.row() )
      {
        const auto rowPk = rows.i64( 0 );
        if( std::none_of( m_rows.begin(), m_rows.end(), [rowPk]( const SearchRow& item ) { return item.rowPk == rowPk; } ) )
          m_rows.push_back( { rowPk, rows.string( 1 ), rows.i64( 2 ), rows.integer( 3 ), rows.string( 4 ), rows.string( 5 ), "text" } );
      }
      if( m_scripts.empty() )
      {
        Statement sourceScripts( m_db, "SELECT source.path,coalesce(script.display_path,''),snippet(lua_source_fts,2,'[',']',' ... ',32),source.provenance FROM lua_source_fts JOIN lua_source_file source ON source.file_id=CAST(lua_source_fts.file_id AS INTEGER) LEFT JOIN lua_script script USING(script_id) WHERE lua_source_fts MATCH ? ORDER BY bm25(lua_source_fts) LIMIT 200" );
        sourceScripts.text( 1, expression.str() );
        while( sourceScripts.row() ) m_scripts.push_back( { 0, sourceScripts.string( 0 ), sourceScripts.string( 1 ), {}, "decompiled_source", {}, sourceScripts.string( 3 ), sourceScripts.string( 2 ), 0, 0 } );
      }
      if( m_scripts.empty() )
      {
        Statement scripts( m_db, "SELECT coalesce(link.row_pk,0),script.display_path,symbol.kind,symbol.symbol,symbol.uses,coalesce(link.confidence,'') FROM lua_fts JOIN lua_script script ON script.script_id=CAST(lua_fts.script_id AS INTEGER) JOIN lua_symbol symbol ON symbol.script_id=script.script_id AND symbol.symbol=lua_fts.symbol LEFT JOIN lua_row_link link ON link.script_id=symbol.script_id AND link.symbol=symbol.symbol WHERE lua_fts MATCH ? ORDER BY bm25(lua_fts) LIMIT 200" );
        scripts.text( 1, expression.str() );
        while( scripts.row() ) m_scripts.push_back( { scripts.i64( 0 ), scripts.string( 1 ), scripts.string( 1 ), scripts.string( 3 ), scripts.string( 2 ), scripts.string( 5 ), "bytecode_only", {}, scripts.integer( 4 ), 0 } );
      }
      Statement source( m_db, "SELECT path,snippet(source_fts,1,'[',']',' ... ',28) FROM source_fts WHERE source_fts MATCH ? ORDER BY bm25(source_fts) LIMIT 100" );
      source.text( 1, expression.str() );
      while( source.row() ) m_sources.push_back( { source.string( 0 ), source.string( 1 ), "FTS", 0 } );
    }
  }
  catch( const std::exception& ex ) { m_error = ex.what(); }
}

std::string Client::DataGraphBrowser::displayJson( const std::string& json )
{
  try
  {
    auto value = Json::parse( json );
    if( value.is_string() ) return value.get< std::string >();
    if( value.is_number_unsigned() )
    {
      const auto number = value.get< uint64_t >();
      if( number <= static_cast< uint64_t >( std::numeric_limits< int64_t >::max() ) ) return formatNumber( static_cast< int64_t >( number ) );
    }
    if( value.is_number_integer() ) return formatNumber( value.get< int64_t >() );
    return value.dump();
  }
  catch( ... ) { return json; }
}

void Client::DataGraphBrowser::selectRow( int64_t rowPk )
{
  if( !open() ) return;
  try
  {
    m_cells.clear(); m_outgoing.clear(); m_incoming.clear(); m_rowScripts.clear(); m_selectedAsset.clear();
    m_exactCandidates.clear(); m_encodedCandidates.clear(); m_offsetCandidates.clear(); m_consumers.clear();
    Statement row( m_db, "SELECT r.sheet_id,s.name,r.main_id,r.ordinal,coalesce(r.display,''),r.values_json,s.consumers_json FROM row_data r JOIN sheet s USING(sheet_id) WHERE row_pk=?" );
    row.integer( 1, rowPk );
    if( !row.row() ) throw std::runtime_error( "Graph row no longer exists" );
    const auto sheetId = row.i64( 0 );
    m_selectedRow = { rowPk, row.string( 1 ), row.i64( 2 ), row.integer( 3 ), row.string( 4 ), {}, {} };
    const auto values = Json::parse( row.string( 5 ) );
    for( const auto& consumer : Json::parse( row.string( 6 ) ) )
      m_consumers.push_back( { consumer.value( "kind", "runtime" ), consumer.value( "lookup", "unresolved" ),
                               consumer.value( "confidence", "candidate" ), consumer.value( "evidence", "" ) } );
    Statement fields( m_db, "SELECT column_index,name,confidence,type_name,fixed_offset FROM field WHERE sheet_id=? ORDER BY column_index" );
    fields.integer( 1, sheetId );
    while( fields.row() )
    {
      const auto column = fields.integer( 0 );
      m_cells.push_back( { column, fields.string( 1 ), fields.string( 2 ), fields.string( 3 ),
                           column < static_cast< int >( values.size() ) ? displayJson( values[ column ].dump() ) : "<missing>", fields.integer( 4 ) } );
    }
    Statement outgoing( m_db, "SELECT coalesce(e.target_row,0),e.target_kind,e.target_name,e.confidence,e.evidence,coalesce(f.name,'') FROM edge e LEFT JOIN field f ON f.field_id=e.source_field WHERE e.source_row=? ORDER BY f.name,e.target_name" );
    outgoing.integer( 1, rowPk );
    while( outgoing.row() )
    {
      const auto kind = outgoing.string( 1 );
      const auto target = outgoing.string( 2 );
      m_outgoing.push_back( { outgoing.i64( 0 ), kind == "row" ? formatRowTarget( target ) : target,
                              outgoing.string( 5 ), outgoing.string( 3 ), outgoing.string( 4 ), kind, target } );
    }
    Statement incoming( m_db, "SELECT e.source_row,s.name,r.main_id,r.ordinal,coalesce(f.name,''),e.confidence,e.evidence FROM edge e JOIN row_data r ON r.row_pk=e.source_row JOIN sheet s USING(sheet_id) LEFT JOIN field f ON f.field_id=e.source_field WHERE e.target_row=? ORDER BY s.name,r.main_id LIMIT 1000" );
    incoming.integer( 1, rowPk );
    while( incoming.row() )
      m_incoming.push_back( { incoming.i64( 0 ), formatRowLabel( incoming.string( 1 ), incoming.i64( 2 ), incoming.integer( 3 ), true ),
                              incoming.string( 4 ), incoming.string( 5 ), incoming.string( 6 ), "row", {} } );

    Statement exact( m_db, "SELECT n.row_pk,s.name,r.main_id,r.ordinal,f.name,n.value FROM number_cell n JOIN row_data r USING(row_pk) JOIN sheet s USING(sheet_id) JOIN field f USING(field_id) WHERE n.value=? AND n.row_pk<>? AND (f.references_json='[]' OR f.references_json LIKE ?) AND NOT EXISTS(SELECT 1 FROM edge e WHERE e.source_row=n.row_pk AND e.source_field=n.field_id AND e.target_row=?) ORDER BY s.name,r.main_id LIMIT 250" );
    exact.integer( 1, m_selectedRow.id ); exact.integer( 2, rowPk );
    exact.text( 3, "%\"" + m_selectedRow.sheet + "\"%" ); exact.integer( 4, rowPk );
    while( exact.row() )
      m_exactCandidates.push_back( { exact.i64( 0 ), formatRowLabel( exact.string( 1 ), exact.i64( 2 ), exact.integer( 3 ), true ),
        exact.string( 4 ) + "=" + formatNumber( exact.i64( 5 ) ), "exact_value_candidate",
        "Exact numeric coincidence only; no resolver from this field to the selected target row is declared.", "row", {} } );

    Statement encoded( m_db, "SELECT n.row_pk,s.name,r.main_id,r.ordinal,f.name,n.value FROM number_cell n JOIN row_data r USING(row_pk) JOIN sheet s USING(sheet_id) JOIN field f USING(field_id) WHERE (n.value & 65535)=? AND n.value<>? AND (f.references_json='[]' OR f.references_json LIKE ?) ORDER BY s.name,r.main_id LIMIT 250" );
    encoded.integer( 1, m_selectedRow.id ); encoded.integer( 2, m_selectedRow.id );
    encoded.text( 3, "%\"" + m_selectedRow.sheet + "\"%" );
    while( encoded.row() )
      m_encodedCandidates.push_back( { encoded.i64( 0 ), formatRowLabel( encoded.string( 1 ), encoded.i64( 2 ), encoded.integer( 3 ), true ),
        encoded.string( 4 ) + "=" + formatNumber( encoded.i64( 5 ) ), "encoded_value_candidate",
        "The stored value's low 16 bits equal the selected row key. This is an encoding hypothesis, not a resolved target domain.", "row", {} } );

    Statement nearby( m_db, "SELECT n.row_pk,s.name,r.main_id,r.ordinal,f.name,n.value,f.references_json,r.values_json,f.sheet_id FROM number_cell n JOIN row_data r USING(row_pk) JOIN sheet s USING(sheet_id) JOIN field f USING(field_id) WHERE n.value BETWEEN ? AND ? AND n.value<>? AND f.references_json<>'[]' AND NOT EXISTS(SELECT 1 FROM edge e WHERE e.source_row=n.row_pk AND e.source_field=n.field_id AND e.target_row=?) ORDER BY abs(n.value-?),s.name,r.main_id LIMIT 500" );
    nearby.integer( 1, m_selectedRow.id - 16 ); nearby.integer( 2, m_selectedRow.id + 16 );
    nearby.integer( 3, m_selectedRow.id ); nearby.integer( 4, rowPk ); nearby.integer( 5, m_selectedRow.id );
    while( nearby.row() )
    {
      const auto sourceValues = Json::parse( nearby.string( 7 ) );
      for( const auto& relation : Json::parse( nearby.string( 6 ) ) )
      {
        bool targetsSheet = false;
        for( const auto& target : relation.value( "targets", Json::array() ) )
          if( target.get< std::string >() == m_selectedRow.sheet ) targetsSheet = true;
        if( !targetsSheet ) continue;
        if( relation.contains( "source_rows" ) )
        {
          bool sourceMatches = false;
          for( const auto& sourceRow : relation[ "source_rows" ] )
            if( sourceRow.get< int64_t >() == nearby.i64( 2 ) ) sourceMatches = true;
          if( !sourceMatches ) continue;
        }
        bool conditionMatches = true;
        if( relation.contains( "when" ) )
        {
          const auto& when = relation[ "when" ];
          Statement conditionField( m_db, "SELECT column_index FROM field WHERE sheet_id=? AND name=?" );
          conditionField.integer( 1, nearby.i64( 8 ) ); conditionField.text( 2, when.value( "field", "" ) );
          conditionMatches = false;
          if( conditionField.row() )
          {
            const auto column = conditionField.integer( 0 );
            if( column >= 0 && column < static_cast< int >( sourceValues.size() ) && sourceValues[ column ].is_number_integer() )
              for( const auto& allowed : when.value( "values", Json::array() ) )
                if( sourceValues[ column ].get< int64_t >() == allowed.get< int64_t >() ) conditionMatches = true;
          }
        }
        if( !conditionMatches ) continue;
        const auto stored = nearby.i64( 5 );
        const auto delta = m_selectedRow.id - stored;
        const auto formula = nearby.string( 4 ) + "=" + formatNumber( stored ) +
          "; target=" + formatNumber( m_selectedRow.id ) + " (stored" + ( delta >= 0 ? "+" : "" ) + std::to_string( delta ) + ")";
        m_offsetCandidates.push_back( { nearby.i64( 0 ), formatRowLabel( nearby.string( 1 ), nearby.i64( 2 ), nearby.integer( 3 ), true ), formula, "offset_hypothesis",
          "This field has a declared resolver to the selected sheet, but no evidence currently establishes this offset. Nearby-key hypothesis only. Resolver evidence: " + relation.value( "evidence", "" ), "row", {} } );
      }
    }
    Statement scripts( m_db, "SELECT link.row_pk,coalesce(source.path,script.display_path),script.display_path,symbol.symbol,symbol.kind,link.confidence,symbol.uses,coalesce(reference.line,0),coalesce(reference.context,''),coalesce(source.provenance,'bytecode_only') FROM lua_row_link link JOIN lua_script script USING(script_id) JOIN lua_symbol symbol USING(script_id,symbol) LEFT JOIN lua_source_file source USING(script_id) LEFT JOIN lua_source_reference reference ON reference.file_id=source.file_id AND reference.symbol=symbol.symbol WHERE link.row_pk=? ORDER BY symbol.symbol,source.path,reference.line,script.display_path" );
    scripts.integer( 1, rowPk );
    while( scripts.row() ) m_rowScripts.push_back( { scripts.i64( 0 ), scripts.string( 1 ), scripts.string( 2 ), scripts.string( 3 ), scripts.string( 4 ), scripts.string( 5 ), scripts.string( 9 ), scripts.string( 8 ), scripts.integer( 6 ), scripts.integer( 7 ) } );
    m_selectedRowPk = rowPk;
  }
  catch( const std::exception& ex ) { m_error = ex.what(); }
}

void Client::DataGraphBrowser::selectAsset( const std::string& path )
{
  if( !open() ) return;
  try
  {
    m_assetChildren.clear(); m_layerSets.clear(); m_placements.clear(); m_timelines.clear(); m_timelineSlots.clear();
    Statement asset( m_db, "SELECT asset_id,kind FROM asset WHERE path=?" ); asset.text( 1, path );
    if( !asset.row() ) throw std::runtime_error( "Asset is not indexed: " + path );
    const auto assetId = asset.i64( 0 ); m_selectedAssetKind = asset.string( 1 ); m_selectedAsset = path;
    Statement children( m_db, "SELECT target.path,target.kind,link.relation,link.confidence FROM asset_edge link JOIN asset target ON target.asset_id=link.target_asset WHERE link.source_asset=? ORDER BY target.path" );
    children.integer( 1, assetId );
    while( children.row() ) m_assetChildren.push_back( { children.string( 0 ), children.string( 1 ), children.string( 2 ), children.string( 3 ) } );
    Statement layers( m_db, "SELECT layer_set_id,territory_type_id,name,coalesce(navmesh_path,''),references_json FROM layer_set WHERE lvb_asset=? ORDER BY layer_set_id" );
    layers.integer( 1, assetId );
    while( layers.row() ) m_layerSets.push_back( { layers.i64( 0 ), layers.i64( 1 ), layers.string( 2 ), layers.string( 3 ), layers.string( 4 ) } );
    Statement count( m_db, "SELECT count(*) FROM placement WHERE lgb_asset=?" ); count.integer( 1, assetId ); count.row(); m_assetPlacementCount = count.i64( 0 );
    Statement placements( m_db, "SELECT group_id,group_name,entry_index,type,type_name,instance_id,name,coalesce(base_id,0),coalesce(sgb_path,'') FROM placement WHERE lgb_asset=? ORDER BY group_id,entry_index LIMIT 2000" );
    placements.integer( 1, assetId );
    while( placements.row() ) m_placements.push_back( { placements.i64( 5 ), placements.i64( 7 ), placements.integer( 3 ), placements.integer( 2 ),
                                                        placements.string( 1 ), placements.string( 4 ), placements.string( 6 ), placements.string( 8 ) } );
    Statement timelines( m_db, "SELECT member_id,name,timeline_id,auto_play,loop_playback,collision_state FROM sgb_timeline WHERE sgb_asset=? ORDER BY member_id" );
    timelines.integer( 1, assetId );
    while( timelines.row() ) m_timelines.push_back( { timelines.integer( 0 ), timelines.integer( 2 ), timelines.integer( 5 ),
                                                       timelines.integer( 3 ) != 0, timelines.integer( 4 ) != 0, timelines.string( 1 ) } );
    Statement slots( m_db, "SELECT slot_index,mask,member_id,coalesce(name,'') FROM sgb_slot WHERE sgb_asset=? ORDER BY slot_index" );
    slots.integer( 1, assetId );
    while( slots.row() ) m_timelineSlots.push_back( { slots.integer( 0 ), slots.integer( 1 ), slots.integer( 2 ), slots.string( 3 ) } );
  }
  catch( const std::exception& ex ) { m_error = ex.what(); }
}

void Client::DataGraphBrowser::navigateRow( int64_t rowPk )
{
  selectRow( rowPk );
  if( m_selectedRowPk != rowPk ) return;
  if( m_historyIndex != static_cast< size_t >( -1 ) && m_history[ m_historyIndex ].rowPk == rowPk ) return;
  if( m_historyIndex + 1 < m_history.size() ) m_history.erase( m_history.begin() + m_historyIndex + 1, m_history.end() );
  auto label = formatRowLabel( m_selectedRow.sheet, m_selectedRow.id, m_selectedRow.ordinal );
  m_history.push_back( { rowPk, {}, std::move( label ) } );
  m_historyIndex = m_history.size() - 1;
}

void Client::DataGraphBrowser::navigateAsset( const std::string& path )
{
  selectAsset( path );
  if( m_selectedAsset != path ) return;
  if( m_historyIndex != static_cast< size_t >( -1 ) && m_history[ m_historyIndex ].assetPath == path ) return;
  if( m_historyIndex + 1 < m_history.size() ) m_history.erase( m_history.begin() + m_historyIndex + 1, m_history.end() );
  auto label = std::filesystem::path( path ).filename().string();
  m_history.push_back( { 0, path, label.empty() ? path : label } );
  m_historyIndex = m_history.size() - 1;
}

void Client::DataGraphBrowser::navigateHistory( size_t index )
{
  if( index >= m_history.size() ) return;
  m_historyIndex = index;
  const auto item = m_history[ index ];
  if( item.rowPk ) selectRow( item.rowPk );
  else selectAsset( item.assetPath );
}

void Client::DataGraphBrowser::showNavigation()
{
  const bool canBack = m_historyIndex != static_cast< size_t >( -1 ) && m_historyIndex > 0;
  const bool canForward = m_historyIndex != static_cast< size_t >( -1 ) && m_historyIndex + 1 < m_history.size();
  ImGui::BeginDisabled( !canBack );
  if( ImGui::SmallButton( "< Back" ) ) navigateHistory( m_historyIndex - 1 );
  ImGui::EndDisabled(); ImGui::SameLine();
  ImGui::BeginDisabled( !canForward );
  if( ImGui::SmallButton( "Forward >" ) ) navigateHistory( m_historyIndex + 1 );
  ImGui::EndDisabled();
  if( m_history.empty() ) return;
  size_t requested = static_cast< size_t >( -1 );
  const auto first = m_historyIndex > 4 ? m_historyIndex - 4 : 0;
  for( size_t i = first; i <= m_historyIndex; ++i )
  {
    if( i != first ) { ImGui::SameLine(); ImGui::TextUnformatted( ">" ); }
    ImGui::SameLine(); ImGui::PushID( static_cast< int >( i ) );
    if( ImGui::SmallButton( m_history[ i ].label.c_str() ) ) requested = i;
    ImGui::PopID();
  }
  if( requested != static_cast< size_t >( -1 ) ) navigateHistory( requested );
}

void Client::DataGraphBrowser::selectSource( const SourceHit& source )
{
  m_selectedSource = source;
  m_sourcePreview = source.snippet;
  if( !source.line || !m_db ) return;
  try
  {
    Statement root( m_db, "SELECT value FROM metadata WHERE key='source_root'" );
    if( !root.row() || root.string( 0 ).empty() ) return;
    std::ifstream input( std::filesystem::path( root.string( 0 ) ) / source.path );
    if( !input ) return;
    std::ostringstream preview;
    std::string line;
    int number = 0;
    while( std::getline( input, line ) )
    {
      ++number;
      if( number + 5 < source.line ) continue;
      if( number > source.line + 5 ) break;
      preview << ( number == source.line ? "> " : "  " ) << number << "  " << line << '\n';
    }
    if( !preview.str().empty() ) m_sourcePreview = preview.str();
  }
  catch( ... ) {}
}

void Client::DataGraphBrowser::selectLuaSource( const ScriptHit& script )
{
  m_selectedLuaPath = script.path;
  m_luaPreview = script.context;
  if( !m_db ) return;
  try
  {
    Statement root( m_db, "SELECT value FROM metadata WHERE key='lua_source_root'" );
    if( !root.row() || root.string( 0 ).empty() ) return;
    std::ifstream input( std::filesystem::path( root.string( 0 ) ) / script.path );
    if( !input ) return;
    std::ostringstream preview;
    std::string line;
    int number = 0;
    while( std::getline( input, line ) )
    {
      ++number;
      if( script.line && number + 10 < script.line ) continue;
      if( script.line && number > script.line + 10 ) break;
      if( !script.line && number > 250 ) { preview << "  ... preview truncated ...\n"; break; }
      preview << ( number == script.line ? "> " : "  " ) << number << "  " << line << '\n';
    }
    if( !preview.str().empty() ) m_luaPreview = preview.str();
  }
  catch( ... ) {}
}

void Client::DataGraphBrowser::showSearchResults()
{
  ImGui::Text( "%zu EXD rows, %zu Lua references, %zu server-source results", m_rows.size(), m_scripts.size(), m_sources.size() );
  if( !m_correction.empty() ) ImGui::TextColored( { 0.95f, 0.75f, 0.25f, 1 }, "Corrections: %s", m_correction.c_str() );
  if( ImGui::BeginTabBar( "GraphSearchTabs" ) )
  {
    if( ImGui::BeginTabItem( "Game data" ) )
    {
      if( ImGui::BeginChild( "GraphRows", ImVec2( 0, 230 ), true ) )
        for( const auto& row : m_rows )
        {
          ImGui::PushID( static_cast< int >( row.rowPk ) );
          auto label = formatRowLabel( row.sheet, row.id, row.ordinal );
          if( !row.display.empty() ) label += "  " + row.display;
          if( ImGui::Selectable( label.c_str(), m_selectedRowPk == row.rowPk ) ) navigateRow( row.rowPk );
          if( !row.snippet.empty() ) { ImGui::SameLine(); ImGui::TextDisabled( "%s", row.snippet.c_str() ); }
          else if( !row.match.empty() ) { ImGui::SameLine(); ImGui::TextDisabled( "[%s]", row.match.c_str() ); }
          ImGui::PopID();
        }
      ImGui::EndChild(); ImGui::EndTabItem();
    }
    if( ImGui::BeginTabItem( "Recovered Lua" ) )
    {
      if( ImGui::BeginChild( "GraphLua", ImVec2( 0, 280 ), true ) )
        for( const auto& script : m_scripts )
        {
          ImGui::PushID( &script );
          if( script.rowPk && ImGui::SmallButton( "EXD definition" ) ) navigateRow( script.rowPk );
          if( script.rowPk ) ImGui::SameLine();
          const auto location = script.path + ( script.line ? ":" + std::to_string( script.line ) : "" );
          if( script.provenance != "bytecode_only" )
          {
            if( ImGui::SmallButton( location.c_str() ) ) selectLuaSource( script );
            ImGui::SameLine(); ImGui::TextDisabled( "[%s]", script.provenance.c_str() );
          }
          else ImGui::TextWrapped( "%s  [%s]", location.c_str(), script.provenance.c_str() );
          if( !script.symbol.empty() )
          {
            ImGui::TextColored( confidenceColor( script.confidence ), "%s  [%s, %d bytecode use%s]", script.symbol.c_str(), script.kind.c_str(), script.uses, script.uses == 1 ? "" : "s" );
          }
          if( !script.context.empty() ) ImGui::TextWrapped( "%s", script.context.c_str() );
          if( !script.bytecodePath.empty() && script.bytecodePath != script.path )
            ImGui::TextDisabled( "Backing bytecode: %s", script.bytecodePath.c_str() );
          ImGui::Separator(); ImGui::PopID();
        }
      ImGui::EndChild();
      if( !m_selectedLuaPath.empty() )
      {
        ImGui::Text( "Recovered source: %s", m_selectedLuaPath.c_str() ); ImGui::SameLine();
        if( ImGui::SmallButton( "Copy Lua path" ) ) ImGui::SetClipboardText( m_selectedLuaPath.c_str() );
        ImGui::InputTextMultiline( "##LuaPreview", m_luaPreview.data(), m_luaPreview.size() + 1,
                                  ImVec2( -1, 220 ), ImGuiInputTextFlags_ReadOnly );
      }
      ImGui::EndTabItem();
    }
    if( ImGui::BeginTabItem( "Server source" ) )
    {
      if( ImGui::BeginChild( "GraphSource", ImVec2( 0, 230 ), true ) )
        for( const auto& source : m_sources )
        {
          ImGui::PushID( &source );
          const auto location = source.path + ( source.line ? ":" + std::to_string( source.line ) : "" );
          if( ImGui::SmallButton( location.c_str() ) ) selectSource( source );
          if( ImGui::IsItemHovered() ) ImGui::SetTooltip( "Show source context" );
          if( !source.semantic.empty() ) { ImGui::SameLine(); ImGui::TextDisabled( "[%s]", source.semantic.c_str() ); }
          ImGui::TextWrapped( "%s", source.snippet.c_str() ); ImGui::Separator();
          ImGui::PopID();
        }
      ImGui::EndChild();
      if( !m_selectedSource.path.empty() )
      {
        if( m_selectedSource.line ) ImGui::Text( "Source: %s:%d", m_selectedSource.path.c_str(), m_selectedSource.line );
        else ImGui::Text( "Source: %s", m_selectedSource.path.c_str() );
        ImGui::SameLine();
        if( ImGui::SmallButton( "Copy path" ) ) ImGui::SetClipboardText( m_selectedSource.path.c_str() );
        ImGui::InputTextMultiline( "##SourcePreview", m_sourcePreview.data(), m_sourcePreview.size() + 1,
                                  ImVec2( -1, 160 ), ImGuiInputTextFlags_ReadOnly );
      }
      ImGui::EndTabItem();
    }
    ImGui::EndTabBar();
  }
}

void Client::DataGraphBrowser::showRowDetail()
{
  if( !m_selectedRowPk ) return;
  int64_t requestedRow = 0;
  std::string requestedAsset;
  auto rowLabel = formatRowLabel( m_selectedRow.sheet, m_selectedRow.id, m_selectedRow.ordinal );
  ImGui::SeparatorText( rowLabel.c_str() );
  if( ImGui::SmallButton( "Open live row in Excel Browser" ) )
  {
    m_excelRequest = { m_selectedRow.sheet, static_cast< uint32_t >( m_selectedRow.id ), static_cast< uint32_t >( m_selectedRow.ordinal ) };
    m_hasExcelRequest = true;
  }
  if( !m_selectedRow.display.empty() ) ImGui::TextWrapped( "%s", m_selectedRow.display.c_str() );
  if( ImGui::BeginTabBar( "GraphDetailTabs" ) )
  {
    if( ImGui::BeginTabItem( "Fields" ) )
    {
      ImGui::Text( "%zu total fields are loaded for this row.", m_cells.size() );
      ImGui::SameLine(); ImGui::TextDisabled( "The table below has its own scrollbar." );
      ImGui::Checkbox( "Sort fields by fixed-byte offset", &m_sortFieldsByOffset );
      ImGui::SameLine(); ImGui::TextDisabled( "EXH column order may differ from in-row storage order." );
      std::vector< const Cell* > cells;
      cells.reserve( m_cells.size() );
      for( const auto& cell : m_cells ) cells.push_back( &cell );
      if( m_sortFieldsByOffset )
        std::stable_sort( cells.begin(), cells.end(), []( const Cell* left, const Cell* right ) {
          if( left->offset != right->offset ) return left->offset < right->offset;
          return left->column < right->column;
        } );
      const auto tableHeight = std::max( 220.0f, ImGui::GetContentRegionAvail().y );
      if( ImGui::BeginTable( "GraphCells", 5, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg | ImGuiTableFlags_Resizable | ImGuiTableFlags_ScrollY, ImVec2( 0, tableHeight ) ) )
      {
        ImGui::TableSetupColumn( "EXH column" ); ImGui::TableSetupColumn( "Field" ); ImGui::TableSetupColumn( "Confidence" ); ImGui::TableSetupColumn( "Type/offset" ); ImGui::TableSetupColumn( "Value" ); ImGui::TableHeadersRow();
        for( const auto* cell : cells )
        {
          ImGui::TableNextRow(); ImGui::TableNextColumn(); ImGui::TextUnformatted( formatNumber( cell->column ).c_str() );
          ImGui::TableNextColumn(); ImGui::TextUnformatted( cell->name.c_str() );
          ImGui::TableNextColumn(); ImGui::TextColored( confidenceColor( cell->confidence ), "%s", cell->confidence.c_str() );
          ImGui::TableNextColumn();
          const auto offset = formatNumber( cell->offset );
          ImGui::Text( "%s @ %s", cell->type.c_str(), offset.c_str() );
          ImGui::TableNextColumn(); ImGui::TextWrapped( "%s", cell->value.c_str() );
        }
        ImGui::EndTable();
      }
      ImGui::EndTabItem();
    }
    if( ImGui::BeginTabItem( "Relations" ) )
    {
      ImGui::Text( "Outgoing (%zu)", m_outgoing.size() );
      for( const auto& link : m_outgoing )
      {
        ImGui::PushID( &link ); ImGui::TextColored( confidenceColor( link.confidence ), "%s", link.confidence.c_str() ); ImGui::SameLine();
        ImGui::Text( "%s ->", link.field.c_str() ); ImGui::SameLine();
        if( ImGui::SmallButton( link.label.c_str() ) )
        {
          if( link.kind == "row" && link.rowPk ) requestedRow = link.rowPk;
          else if( link.kind == "asset" ) requestedAsset = link.target;
        }
        if( ImGui::IsItemHovered() && !link.evidence.empty() ) ImGui::SetTooltip( "%s", link.evidence.c_str() );
        ImGui::PopID();
      }
      if( !m_rowScripts.empty() )
      {
        ImGui::Separator(); ImGui::Text( "Lua references (%zu)", m_rowScripts.size() );
        for( const auto& script : m_rowScripts )
        {
          ImGui::TextColored( confidenceColor( script.confidence ), "%s", script.confidence.c_str() ); ImGui::SameLine();
          const auto location = script.path + ( script.line ? ":" + std::to_string( script.line ) : "" );
          ImGui::TextWrapped( "%s uses %s (%s, %d bytecode use%s)", location.c_str(), script.symbol.c_str(), script.kind.c_str(),
                              script.uses, script.uses == 1 ? "" : "s" );
          if( !script.context.empty() ) ImGui::TextWrapped( "%s", script.context.c_str() );
          if( !script.bytecodePath.empty() && script.bytecodePath != script.path )
            ImGui::TextDisabled( "Backing bytecode: %s", script.bytecodePath.c_str() );
        }
      }
      ImGui::Separator(); ImGui::Text( "Incoming resolved relations (%zu)", m_incoming.size() );
      for( const auto& link : m_incoming )
      {
        ImGui::PushID( &link );
        if( ImGui::SmallButton( link.label.c_str() ) ) requestedRow = link.rowPk;
        ImGui::SameLine(); ImGui::TextColored( confidenceColor( link.confidence ), "%s via %s", link.confidence.c_str(), link.field.c_str() );
        if( ImGui::IsItemHovered() && !link.evidence.empty() ) ImGui::SetTooltip( "%s", link.evidence.c_str() );
        ImGui::PopID();
      }

      if( !m_consumers.empty() )
      {
        ImGui::Separator(); ImGui::Text( "Runtime lookup paths (%zu)", m_consumers.size() );
        ImGui::TextDisabled( "These prove how this sheet can be addressed, not which event produces this specific row ID." );
        for( const auto& consumer : m_consumers )
        {
          ImGui::TextColored( confidenceColor( consumer.confidence ), "%s", consumer.confidence.c_str() ); ImGui::SameLine();
          ImGui::TextWrapped( "%s: %s", consumer.kind.c_str(), consumer.lookup.c_str() );
          if( ImGui::IsItemHovered() && !consumer.evidence.empty() ) ImGui::SetTooltip( "%s", consumer.evidence.c_str() );
        }
      }

      auto showCandidates = [&]( const char* title, const std::vector< Link >& candidates ) {
        if( candidates.empty() ) return;
        ImGui::Separator(); ImGui::Text( "%s (%zu)", title, candidates.size() );
        for( const auto& candidate : candidates )
        {
          ImGui::PushID( &candidate );
          ImGui::TextColored( confidenceColor( candidate.confidence ), "%s", candidate.confidence.c_str() ); ImGui::SameLine();
          if( ImGui::SmallButton( candidate.label.c_str() ) ) requestedRow = candidate.rowPk;
          ImGui::SameLine(); ImGui::TextWrapped( "via %s", candidate.field.c_str() );
          if( ImGui::IsItemHovered() && !candidate.evidence.empty() ) ImGui::SetTooltip( "%s", candidate.evidence.c_str() );
          ImGui::PopID();
        }
      };
      ImGui::SeparatorText( "Speculative discovery (not graph edges)" );
      ImGui::TextDisabled( "Candidates intentionally preserve ambiguity; equal or nearby IDs are not foreign-key proof." );
      showCandidates( "Declared-domain nearby/offset hypotheses (+/-16)", m_offsetCandidates );
      showCandidates( "Exact numeric coincidences", m_exactCandidates );
      showCandidates( "Low-16-bit encoding hypotheses", m_encodedCandidates );
      ImGui::EndTabItem();
    }
    ImGui::EndTabBar();
  }
  if( requestedRow ) navigateRow( requestedRow );
  else if( !requestedAsset.empty() ) navigateAsset( requestedAsset );
}

void Client::DataGraphBrowser::showAssetDetail()
{
  if( m_selectedAsset.empty() ) return;
  std::string requestedAsset;
  int64_t requestedSearchId = 0;
  ImGui::SeparatorText( "Asset" ); ImGui::TextWrapped( "%s [%s]", m_selectedAsset.c_str(), m_selectedAssetKind.c_str() );
  if( !m_layerSets.empty() )
  {
    ImGui::Text( "Layer sets (%zu)", m_layerSets.size() );
    for( const auto& layer : m_layerSets )
    {
      ImGui::PushID( &layer );
      const auto label = "Layer set " + formatNumber( layer.id ) + ": " + layer.name;
      if( ImGui::TreeNode( label.c_str() ) )
      {
        ImGui::Text( "TerritoryType: %s", formatNumber( layer.territoryTypeId ).c_str() );
        if( !layer.navmeshPath.empty() ) ImGui::TextWrapped( "Navmesh: %s", layer.navmeshPath.c_str() );
        ImGui::TextWrapped( "References: %s", layer.references.c_str() );
        ImGui::TreePop();
      }
      ImGui::PopID();
    }
  }
  if( !m_assetChildren.empty() )
  {
    ImGui::Text( "Children (%zu)", m_assetChildren.size() );
    for( const auto& child : m_assetChildren )
    {
      ImGui::PushID( &child );
      if( ImGui::SmallButton( child.path.c_str() ) ) requestedAsset = child.path;
      ImGui::SameLine(); ImGui::TextDisabled( "%s / %s / %s", child.kind.c_str(), child.relation.c_str(), child.confidence.c_str() );
      ImGui::PopID();
    }
  }
  if( !m_timelines.empty() )
  {
    ImGui::Text( "SGB timelines (%zu)", m_timelines.size() );
    if( ImGui::BeginTable( "SgbTimelines", 6, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg | ImGuiTableFlags_Resizable ) )
    {
      for( const char* heading : { "Member", "Name", "Timeline", "Auto", "Loop", "Collision" } ) ImGui::TableSetupColumn( heading );
      ImGui::TableHeadersRow();
      for( const auto& timeline : m_timelines )
      {
        ImGui::TableNextRow(); ImGui::TableNextColumn(); ImGui::TextUnformatted( formatNumber( timeline.memberId ).c_str() );
        ImGui::TableNextColumn(); ImGui::TextUnformatted( timeline.name.c_str() );
        ImGui::TableNextColumn(); ImGui::TextUnformatted( formatNumber( timeline.timelineId ).c_str() );
        ImGui::TableNextColumn(); ImGui::TextUnformatted( timeline.autoPlay ? "yes" : "no" );
        ImGui::TableNextColumn(); ImGui::TextUnformatted( timeline.loopPlayback ? "yes" : "no" );
        ImGui::TableNextColumn(); ImGui::TextUnformatted( formatNumber( timeline.collisionState ).c_str() );
      }
      ImGui::EndTable();
    }
    if( ImGui::TreeNode( "General-purpose slots" ) )
    {
      for( const auto& slot : m_timelineSlots )
      {
        const auto index = formatNumber( slot.index );
        const auto mask = formatNumber( slot.mask );
        const auto member = formatNumber( slot.memberId );
        ImGui::BulletText( "%s: mask %s -> member %s %s", index.c_str(), mask.c_str(), member.c_str(), slot.name.c_str() );
      }
      ImGui::TreePop();
    }
  }
  if( m_assetPlacementCount )
  {
    ImGui::Text( "Placements: %lld (showing %zu)", static_cast< long long >( m_assetPlacementCount ), m_placements.size() );
    if( ImGui::BeginTable( "Placements", 6, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg | ImGuiTableFlags_Resizable | ImGuiTableFlags_ScrollY, ImVec2( 0, 300 ) ) )
    {
      for( const char* heading : { "Group", "Type", "Instance", "Base ID", "Name", "SGB" } ) ImGui::TableSetupColumn( heading );
      ImGui::TableHeadersRow();
      for( const auto& placement : m_placements )
      {
        ImGui::PushID( &placement );
        ImGui::TableNextRow(); ImGui::TableNextColumn(); ImGui::TextUnformatted( placement.group.c_str() );
        ImGui::TableNextColumn(); ImGui::TextUnformatted( placement.typeName.c_str() );
        ImGui::TableNextColumn(); ImGui::TextUnformatted( formatNumber( placement.instanceId ).c_str() );
        ImGui::TableNextColumn();
        if( placement.baseId )
        {
          const auto baseLabel = formatNumber( placement.baseId );
          if( ImGui::SmallButton( baseLabel.c_str() ) ) requestedSearchId = placement.baseId;
          if( ImGui::IsItemHovered() ) ImGui::SetTooltip( "Search this ID across all EXD domains and source" );
        }
        ImGui::TableNextColumn(); ImGui::TextUnformatted( placement.name.c_str() );
        ImGui::TableNextColumn();
        if( !placement.sgbPath.empty() && ImGui::SmallButton( placement.sgbPath.c_str() ) ) requestedAsset = placement.sgbPath;
        ImGui::PopID();
      }
      ImGui::EndTable();
    }
  }
  if( !requestedAsset.empty() ) navigateAsset( requestedAsset );
  else if( requestedSearchId )
  {
    const auto query = "id:" + std::to_string( requestedSearchId );
    std::snprintf( m_searchBuffer, sizeof( m_searchBuffer ), "%s", query.c_str() );
    search();
  }
}

void Client::DataGraphBrowser::show()
{
  if( !ImGui::Begin( "PS3 Data Graph" ) ) { ImGui::End(); return; }
  if( !m_db )
  {
    ImGui::TextWrapped( "Database: %s", m_path.string().c_str() );
    if( ImGui::Button( "Open graph" ) ) open();
    if( !m_error.empty() ) ImGui::TextColored( { 0.9f, 0.25f, 0.25f, 1 }, "%s", m_error.c_str() );
    ImGui::End(); return;
  }
  showNavigation();
  ImGui::SetNextItemWidth( -100 );
  const bool enter = ImGui::InputTextWithHint( "##GraphSearch", "text, 0xF001A, or id:0xF001A", m_searchBuffer, sizeof( m_searchBuffer ), ImGuiInputTextFlags_EnterReturnsTrue );
  ImGui::SameLine();
  if( ImGui::Button( "Search" ) || enter ) search();
  if( !m_error.empty() ) ImGui::TextColored( { 0.9f, 0.25f, 0.25f, 1 }, "%s", m_error.c_str() );
  showSearchResults();
  showRowDetail();
  showAssetDetail();
  ImGui::End();
}
