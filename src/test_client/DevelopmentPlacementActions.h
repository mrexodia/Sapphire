#pragma once
#include "Protocol.h"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <set>

namespace Sapphire::Testing
{
  // Administrative setup only. This does NOT authorize a server-side mutation:
  // the disabled-by-default server command independently checks the registry,
  // GM permission, exact targets, world-thread state and its one-shot ledger.
  class DevelopmentPlacementActions
  {
  public:
    std::string consume(const nlohmann::json& state, bool moving, const nlohmann::json& args)
    {
      using Json = nlohmann::json;
      try
      {
        if(!args.is_object() || args.size() != 4 || args.at("administrative_setup") != true ||
           !args.at("approval_id").is_string() || !args.at("slot").is_number_integer())
          throw ProtocolError("explicit typed development placement approval required");
        const auto approval = args.at("approval_id").get<std::string>();
        const auto slot = args.at("slot").get<int64_t>();
        if(approval.size() != 32 || !std::all_of(approval.begin(), approval.end(),
              [](char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }) ||
           (slot != 0 && slot != 1))
          throw ProtocolError("development placement requires one approval and slot 0 or 1");
        const auto& owner = args.at("expected_operator");
        if(!owner.is_object() || owner.size() != 3 || !owner.at("name").is_string() ||
           !positive(owner.at("entity_id"), UINT32_MAX) || !positive(owner.at("character_id"), UINT64_MAX))
          throw ProtocolError("exact received operator identity required");
        const auto name = owner.at("name").get<std::string>();
        if(name.empty() || name.size() >= 32 || !std::all_of(name.begin(), name.end(),
              [](unsigned char c) { return c >= 32 && c <= 126; }))
          throw ProtocolError("bounded operator name required");
        if(state.at("phase") != "ready" || moving || state.at("territory") != 130 ||
           !positive(state.at("gm_rank"), 255) || state.at("entity_id") != owner.at("entity_id") ||
           !state.at("scene").is_null() || !state.at("event_id").is_null() ||
           state.at("between_areas") != false || state.at("party").at("id") != 0 ||
           state.at("party").at("count") != 0 || !state.at("pending_party_invite").is_null())
          throw ProtocolError("development operator must be ready, stationary, nonparty GM in public Uldah");
        if(!state.at("characters").is_array())
          throw ProtocolError("received operator character list required");
        size_t matches = 0;
        for(const auto& row : state.at("characters"))
        {
          if(row.at("name") != name) continue;
          ++matches;
          if(row.at("entity_id") != owner.at("entity_id") || row.at("character_id") != owner.at("character_id"))
            throw ProtocolError("operator lobby/world identity mismatch");
        }
        if(matches != 1)
          throw ProtocolError("ambiguous or missing operator lobby identity");
        if((!m_approval.empty() && m_approval != approval) || m_slots.count(static_cast<int>(slot)))
          throw ProtocolError("operator approval changed or already consumed; do not retry an uncertain placement");
        // Consume BEFORE transport publication, including if publication throws.
        // At most two requests and one registry approval per Bot lifetime.
        m_approval = approval;
        m_slots.insert(static_cast<int>(slot));
        return "!devbot place " + approval + " " + std::to_string(slot);
      }
      catch(const nlohmann::json::exception&)
      {
        throw ProtocolError("invalid typed development placement identity/state");
      }
    }
  private:
    static bool positive(const nlohmann::json& value, uint64_t maximum)
    {
      if(!value.is_number_integer() || (!value.is_number_unsigned() && value.get<int64_t>() <= 0))
        return false;
      const auto number = value.get<uint64_t>();
      return number > 0 && number <= maximum;
    }
    std::string m_approval;
    std::set<int> m_slots;
  };
}
