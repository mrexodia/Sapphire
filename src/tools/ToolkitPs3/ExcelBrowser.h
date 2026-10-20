#pragma once
#include "imgui.h"
#include "ExdData.h"
#include "DataGraphBrowser.h"

namespace Client
{
  class ExcelBrowser
  {
  public:
    bool show( Data::ExdData& data, DataGraphBrowser& graph );
    void openRow( const std::string& sheet, uint32_t id, uint32_t ordinal = 0 );
    void reset();
  private:
    bool contents( Data::ExdData& data, DataGraphBrowser& graph );
    ImGuiTextFilter m_filter;
    std::string m_name, m_loadedName;
    xivps3::exd::Language m_language{ xivps3::exd::Language::en };
    xivps3::exd::Language m_loadedLanguage{ xivps3::exd::Language::en };
    std::vector< uint32_t > m_ids;
    std::vector< DataGraphBrowser::SemanticField > m_semanticFields;
    uint32_t m_id{ 0 }, m_ordinal{ 0 };
    uint32_t m_pendingId{}, m_pendingOrdinal{};
    bool m_hasPendingRow{};
    bool m_sortByPhysicalOffset{};
  };
}
