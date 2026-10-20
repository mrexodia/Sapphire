#pragma once

#include "imgui.h"
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

struct sqlite3;

namespace Client
{
  class DataGraphBrowser
  {
  public:
    struct SemanticField
    {
      int column{};
      std::string name, confidence, evidence, references;
    };
    struct ExcelRequest
    {
      std::string sheet;
      uint32_t id{}, ordinal{};
    };

    DataGraphBrowser() = default;
    ~DataGraphBrowser();
    DataGraphBrowser( const DataGraphBrowser& ) = delete;
    DataGraphBrowser& operator=( const DataGraphBrowser& ) = delete;

    void setDatabasePath( const std::filesystem::path& path );
    void show();
    void reset();
    bool openRow( const std::string& sheet, uint32_t id, uint32_t ordinal = 0 );
    bool openFieldReference( const std::string& sheet, uint32_t id, uint32_t ordinal, int column );
    void searchFor( const std::string& text );
    std::vector< SemanticField > semanticFields( const std::string& sheet );
    bool takeExcelRequest( ExcelRequest& request );

  private:
    struct SearchRow
    {
      int64_t rowPk{};
      std::string sheet;
      int64_t id{};
      int ordinal{};
      std::string display;
      std::string snippet;
      std::string match;
    };
    struct SourceHit { std::string path, snippet, semantic; int line{}; };
    struct ScriptHit
    {
      int64_t rowPk{};
      std::string path, bytecodePath, symbol, kind, confidence, provenance, context;
      int uses{}, line{};
    };
    struct Cell
    {
      int column{};
      std::string name, confidence, type, value;
      int offset{};
    };
    struct Link
    {
      int64_t rowPk{};
      std::string label, field, confidence, evidence, kind, target;
    };
    struct Consumer
    {
      std::string kind, lookup, confidence, evidence;
    };
    struct AssetChild { std::string path, kind, relation, confidence; };
    struct LayerSet
    {
      int64_t id{}, territoryTypeId{};
      std::string name, navmeshPath, references;
    };
    struct Placement
    {
      int64_t instanceId{}, baseId{};
      int type{}, entryIndex{};
      std::string group, typeName, name, sgbPath;
    };
    struct Timeline
    {
      int memberId{}, timelineId{}, collisionState{};
      bool autoPlay{}, loopPlayback{};
      std::string name;
    };
    struct TimelineSlot
    {
      int index{}, mask{}, memberId{};
      std::string name;
    };
    struct HistoryItem
    {
      int64_t rowPk{};
      std::string assetPath, label;
    };

    bool open();
    void close();
    void search();
    void selectRow( int64_t rowPk );
    void selectAsset( const std::string& path );
    void navigateRow( int64_t rowPk );
    void navigateAsset( const std::string& path );
    void navigateHistory( size_t index );
    void showNavigation();
    void showSearchResults();
    void showRowDetail();
    void showAssetDetail();
    void selectSource( const SourceHit& source );
    void selectLuaSource( const ScriptHit& script );
    std::vector< std::string > queryTerms( const std::string& query );
    static std::string displayJson( const std::string& json );

    sqlite3* m_db{};
    std::filesystem::path m_path;
    std::string m_error, m_correction;
    char m_searchBuffer[ 256 ]{};
    std::vector< SearchRow > m_rows;
    std::vector< SourceHit > m_sources;
    std::vector< ScriptHit > m_scripts, m_rowScripts;
    SourceHit m_selectedSource;
    std::string m_sourcePreview;
    std::string m_selectedLuaPath, m_luaPreview;

    int64_t m_selectedRowPk{};
    SearchRow m_selectedRow;
    std::vector< Cell > m_cells;
    std::vector< Link > m_outgoing, m_incoming;
    std::vector< Link > m_exactCandidates, m_encodedCandidates, m_offsetCandidates;
    std::vector< Consumer > m_consumers;

    std::string m_selectedAsset;
    std::string m_selectedAssetKind;
    std::vector< AssetChild > m_assetChildren;
    std::vector< LayerSet > m_layerSets;
    std::vector< Placement > m_placements;
    std::vector< Timeline > m_timelines;
    std::vector< TimelineSlot > m_timelineSlots;
    int64_t m_assetPlacementCount{};
    std::vector< HistoryItem > m_history;
    size_t m_historyIndex{ static_cast< size_t >( -1 ) };
    ExcelRequest m_excelRequest;
    bool m_hasExcelRequest{};
    bool m_sortFieldsByOffset{};
  };
}
