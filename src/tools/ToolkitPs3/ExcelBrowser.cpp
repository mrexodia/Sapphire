#include "ExcelBrowser.h"
#include <algorithm>
#include <iomanip>
#include <sstream>

namespace
{
  const char* languageName( xivps3::exd::Language language )
  {
    static const char* names[] = { "Neutral", "Japanese", "English", "German", "French", "Chinese (simplified)", "Chinese (traditional)", "Korean" };
    auto value = static_cast< unsigned >( language );
    return value < 8 ? names[ value ] : "Unknown";
  }

  template< typename T >
  std::string formatNumber( T value, bool includeHex = true )
  {
    std::ostringstream out;
    if constexpr( std::is_same_v< T, int8_t > || std::is_same_v< T, uint8_t > ) out << int( value );
    else out << value;
    if( includeHex && value >= 10 )
      out << " (0x" << std::uppercase << std::hex << static_cast< uint64_t >( value ) << ')';
    return out.str();
  }

  std::string displayCell( const xivps3::exd::Field& field, bool includeHex = true )
  {
    return std::visit( [includeHex]( const auto& value ) -> std::string {
      using T = std::decay_t< decltype( value ) >;
      if constexpr( std::is_same_v< T, std::string > )
      {
        std::ostringstream out;
        for( unsigned char c : value )
        {
          if( c < 32 || c == 127 ) out << "\\x" << std::hex << std::setw( 2 ) << std::setfill( '0' ) << unsigned( c );
          else out << static_cast< char >( c );
        }
        return out.str();
      }
      else if constexpr( std::is_same_v< T, bool > ) return value ? "true" : "false";
      else if constexpr( std::is_same_v< T, xivps3::exd::binary::HalfBits > )
      {
        std::ostringstream out;
        out << value.bits << " (0x" << std::uppercase << std::hex << std::setw( 4 ) << std::setfill( '0' ) << value.bits << ", F16 bits)";
        return out.str();
      }
      else if constexpr( std::is_integral_v< T > ) return formatNumber( value, includeHex );
      else
      {
        std::ostringstream out;
        out << std::setprecision( 9 ) << value;
        return out.str();
      }
    }, field );
  }
}

void Client::ExcelBrowser::reset()
{
  m_name.clear();
  m_loadedName.clear();
  m_ids.clear();
  m_semanticFields.clear();
  m_id = m_ordinal = 0;
  m_language = m_loadedLanguage = xivps3::exd::Language::en;
  m_hasPendingRow = false;
}

void Client::ExcelBrowser::openRow( const std::string& sheet, uint32_t id, uint32_t ordinal )
{
  m_name = sheet;
  m_language = xivps3::exd::Language::en;
  m_loadedName.clear();
  m_pendingId = id;
  m_pendingOrdinal = ordinal;
  m_hasPendingRow = true;
}

bool Client::ExcelBrowser::show( Data::ExdData& data, DataGraphBrowser& graph )
{
  bool openGraph = false;
  if( ImGui::Begin( "Excel Browser" ) )
  {
    try { openGraph = contents( data, graph ); }
    catch( const std::exception& ex ) { ImGui::TextWrapped( "Sheet read failed: %s", ex.what() ); }
  }
  ImGui::End();
  return openGraph;
}

bool Client::ExcelBrowser::contents( Data::ExdData& data, DataGraphBrowser& graph )
{
  const auto& names = data.getSheetNames();
  ImGui::Text( "%zu root-listed sheets. Columns are schema indices, not verified foreign keys.", names.size() );
  m_filter.Draw( "Filter sheets" );
  if( ImGui::BeginChild( "Sheet catalog", ImVec2( 0, 180 ), true ) )
  {
    for( const auto& name : names )
      if( m_filter.PassFilter( name.c_str() ) && ImGui::Selectable( name.c_str(), m_name == name ) )
      {
        m_name = name;
        m_language = xivps3::exd::Language::en;
        m_loadedName.clear();
      }
  }
  ImGui::EndChild();
  if( m_name.empty() ) return false;

  const auto& cat = data.getCategory( m_name );
  const auto& h = cat.get_header().get_binary_header();
  const auto& languages = cat.get_header().get_languages();
  if( languages.empty() ) { ImGui::TextUnformatted( "No declared languages." ); return false; }
  if( std::find( languages.begin(), languages.end(), m_language ) == languages.end() )
  {
    const auto neutral = std::find( languages.begin(), languages.end(), xivps3::exd::Language::none );
    m_language = neutral != languages.end() ? *neutral : languages.front();
  }
  if( ImGui::BeginCombo( "Language", languageName( m_language ) ) )
  {
    for( auto language : languages )
      if( ImGui::Selectable( languageName( language ), m_language == language ) ) m_language = language;
    ImGui::EndCombo();
  }
  const auto& sheet = cat.get_data_ln( m_language );
  if( m_loadedName != m_name || m_loadedLanguage != m_language )
  {
    m_ids = sheet.get_ids();
    m_id = m_ids.empty() ? 0 : m_ids.front();
    m_ordinal = 0;
    if( m_hasPendingRow )
    {
      m_id = m_pendingId;
      m_ordinal = m_pendingOrdinal;
      m_hasPendingRow = false;
    }
    m_semanticFields = graph.semanticFields( m_name );
    m_loadedName = m_name;
    m_loadedLanguage = m_language;
  }
  ImGui::Text( "EXH v%u | fixed bytes %u | keys %u | columns %zu | pages %zu | main IDs %zu",
               h.version, h.fixedSize, h.keyCount, h.columns.size(), h.pages.size(), m_ids.size() );
  ImGui::TextUnformatted( "Values come live from the PS3 SqPack. Semantic names and links come from the generated graph." );
  if( m_ids.empty() ) return false;
  if( ImGui::BeginCombo( "Main row ID", formatNumber( m_id ).c_str() ) )
  {
    ImGuiListClipper clipper;
    clipper.Begin( static_cast< int >( m_ids.size() ) );
    while( clipper.Step() )
      for( int i = clipper.DisplayStart; i < clipper.DisplayEnd; ++i )
        if( ImGui::Selectable( formatNumber( m_ids[ i ] ).c_str(), m_id == m_ids[ i ] ) ) { m_id = m_ids[ i ]; m_ordinal = 0; }
    ImGui::EndCombo();
  }
  if( ImGui::InputScalar( "Jump to main ID", ImGuiDataType_U32, &m_id ) ) m_ordinal = 0;
  if( !std::binary_search( m_ids.begin(), m_ids.end(), m_id ) ) { ImGui::TextUnformatted( "Main ID not present." ); return false; }
  const auto count = sheet.get_subrow_count( m_id );
  ImGui::Text( "%zu subrows; ordinal and stored key IDs are different.", count );
  ImGui::InputScalar( "Subrow ordinal", ImGuiDataType_U32, &m_ordinal );
  if( m_ordinal >= count ) { ImGui::TextUnformatted( "Subrow ordinal out of range." ); return false; }
  const auto keys = sheet.get_subrow_keys( m_id, m_ordinal );
  for( size_t i = 0; i < keys.size(); ++i ) { ImGui::SameLine(); ImGui::Text( "key%zu = %s", i + 1, formatNumber( keys[ i ] ).c_str() ); }
  bool openGraph = false;
  if( ImGui::Button( "Show this row and its relations in Data Graph" ) )
  {
    graph.openRow( m_name, m_id, m_ordinal );
    openGraph = true;
  }
  const auto fields = sheet.get_row( m_id, m_ordinal ); // decode before opening table, so errors leave ImGui balanced
  ImGui::Checkbox( "Sort fields by fixed-byte offset", &m_sortByPhysicalOffset );
  ImGui::SameLine(); ImGui::TextDisabled( "EXH column order may differ from in-row storage order." );
  std::vector< size_t > fieldOrder( fields.size() );
  for( size_t i = 0; i < fieldOrder.size(); ++i ) fieldOrder[ i ] = i;
  if( m_sortByPhysicalOffset )
    std::stable_sort( fieldOrder.begin(), fieldOrder.end(), [&]( size_t left, size_t right ) {
      if( h.columns[ left ].offset != h.columns[ right ].offset ) return h.columns[ left ].offset < h.columns[ right ].offset;
      return h.columns[ left ].type < h.columns[ right ].type;
    } );
  if( ImGui::BeginTable( "Cells", 7, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg | ImGuiTableFlags_Resizable ) )
  {
    ImGui::TableSetupColumn( "EXH column" ); ImGui::TableSetupColumn( "Semantic name" );
    ImGui::TableSetupColumn( "Confidence" ); ImGui::TableSetupColumn( "Reference" ); ImGui::TableSetupColumn( "Type" );
    ImGui::TableSetupColumn( "Fixed offset" ); ImGui::TableSetupColumn( "Value (right-click for graph search)" );
    ImGui::TableHeadersRow();
    for( const auto i : fieldOrder )
    {
      ImGui::PushID( static_cast< int >( i ) );
      ImGui::TableNextRow(); ImGui::TableNextColumn(); ImGui::TextUnformatted( formatNumber( i ).c_str() );
      const auto semantic = i < m_semanticFields.size() ? m_semanticFields[ i ] : DataGraphBrowser::SemanticField{ static_cast< int >( i ), "Column" + std::to_string( i ), "physical_only", "Physical EXH column; no semantic label evidence.", {} };
      ImGui::TableNextColumn(); ImGui::TextUnformatted( semantic.name.c_str() );
      ImGui::TableNextColumn(); ImGui::TextDisabled( "%s", semantic.confidence.c_str() );
      if( ImGui::IsItemHovered() && !semantic.evidence.empty() ) ImGui::SetTooltip( "%s", semantic.evidence.c_str() );
      ImGui::TableNextColumn();
      if( !semantic.references.empty() )
      {
        if( ImGui::SmallButton( semantic.references.c_str() ) )
        {
          graph.openFieldReference( m_name, m_id, m_ordinal, static_cast< int >( i ) );
          openGraph = true;
        }
        if( ImGui::IsItemHovered() ) ImGui::SetTooltip( "Open the evidence-qualified target or relation candidates" );
      }
      else ImGui::TextDisabled( "-" );
      ImGui::TableNextColumn(); ImGui::Text( "%s (%s)", xivps3::exd::binary::typeName( h.columns[ i ].type ), formatNumber( h.columns[ i ].type ).c_str() );
      ImGui::TableNextColumn(); ImGui::TextUnformatted( formatNumber( h.columns[ i ].offset ).c_str() );
      ImGui::TableNextColumn();
      const auto value = displayCell( fields[ i ] );
      const auto searchValue = displayCell( fields[ i ], false );
      if( semantic.name == "Symbol" )
      {
        if( ImGui::SmallButton( value.c_str() ) ) { graph.searchFor( value ); openGraph = true; }
        if( ImGui::IsItemHovered() ) ImGui::SetTooltip( "Find this symbol's EXD definition and Lua references" );
      }
      else ImGui::TextUnformatted( value.c_str() );
      if( ImGui::BeginPopupContextItem( "Cell" ) )
      {
        if( ImGui::MenuItem( "Copy displayed value" ) ) ImGui::SetClipboardText( value.c_str() );
        if( ImGui::MenuItem( "Search exact value in Data Graph" ) ) { graph.searchFor( searchValue ); openGraph = true; }
        ImGui::EndPopup();
      }
      ImGui::PopID();
    }
    ImGui::EndTable();
  }
  return openGraph;
}
