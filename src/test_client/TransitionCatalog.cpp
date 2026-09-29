// Local asset inspection only: no connections, character changes, or gameplay calls.
#include <Exd/ExdData.h>
#include <Logging/Logger.h>
#include <GameData.h>
#include <File.h>
#include <datReader/DatCategories/bg/lgb.h>
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
#include <map>
#include <cmath>
#include <filesystem>
#include <Navi/NaviProvider.h>
#include <DetourNavMeshQuery.h>
#include "NavigationRoute.h"

using Json = nlohmann::json;
static Json vector(const vec3& p) { return {p.x, p.y, p.z}; }

static Json objects(Sapphire::Data::ExdData& data, uint16_t territory, Json& ignoredOptional)
{
  auto row = data.getRow<Excel::TerritoryType>(territory);
  if(!row) throw std::runtime_error("missing territory metadata");
  auto path = row->getString(row->data().LVB);
  auto level = path.find("/level/");
  if(level == std::string::npos) throw std::runtime_error("territory has no level path");
  path = "bg/" + path.substr(0, level) + "/level/";
  Json result = Json::array();
  LGB_GROUP::AssetTypeFilter filter = [](eAssetType type) {
    return type == eAssetType::ExitRange || type == eAssetType::PopRange || type == eAssetType::MapRange;
  };
  for(const auto* name : {"bg", "planmap", "planevent", "planner"})
  {
    const auto filePath = path + name + ".lgb";
    if(!data.getGameData()->doesFileExist(filePath))
    {
      if(std::string(name) != "planner") throw std::runtime_error("missing required level layer: " + filePath);
      ignoredOptional.push_back({{"file", filePath}, {"reason", "optional layer absent"}});
      continue;
    }
    auto file = data.getGameData()->getFile(filePath);
    auto section = file->access_data_sections().at(0);
    if(section.size() < sizeof(LGB_FILE_HEADER) || std::memcmp(section.data(), "LGB1", 4) ||
       std::memcmp(section.data() + 12, "LGP1", 4))
    {
      // InstanceObjectCache explicitly falls back to the three required layers
      // when the optional planner file cannot be parsed. Record that limitation.
      if(std::string(name) != "planner") throw std::runtime_error("unsupported level section: " + filePath);
      ignoredOptional.push_back({{"file", filePath}, {"reason", "not a supported LGB1/LGP1 layer"}});
      continue;
    }
    LGB_FILE lgb(section.data(), name, &filter);
    for(const auto& group : lgb.groups)
      for(const auto& entry : group.entries)
      {
        const auto& h = entry->header;
        Json object{{"id", h.InstanceID}, {"territory", territory},
                    {"position", vector(h.Transformation.Translation)},
                    {"rotation", vector(h.Transformation.Rotation)},
                    {"scale", vector(h.Transformation.Scale)}};
        if(entry->getType() == eAssetType::ExitRange)
        {
          const auto& exit = std::static_pointer_cast<ExitRangeEntry>(entry)->header;
          object["kind"] = "exit";
          object["enabled"] = exit.triggerBoxType.enabled != 0;
          object["shape"] = static_cast<int>(exit.triggerBoxType.triggerBoxShape);
          object["exit_type"] = exit.exitType;
          object["target_territory"] = exit.destTerritoryType;
          object["target_pop"] = exit.destInstanceObjectId;
        }
        else if(entry->getType() == eAssetType::MapRange)
        {
          const auto& range = std::static_pointer_cast<MapRangeEntry>(entry)->header;
          object["kind"] = "map_range";
          object["enabled"] = range.triggerBoxType.enabled != 0;
          object["shape"] = static_cast<int>(range.triggerBoxType.triggerBoxShape);
          object["discovery_enabled"] = range.discoveryEnabled != 0;
          object["discovery_index"] = range.discoveryIndex;
        }
        else object["kind"] = "pop";
        result.push_back(std::move(object));
      }
  }
  return result;
}

int main(int argc, char** argv)
{
  if(argc != 3 && argc != 5)
  { std::cerr << "Usage: sapphire_test_transitions <game/sqpack> [<mesh-root>] <private-output.json> [exit-id]\n"; return 2; }
  try
  {
    Sapphire::Logger::init("log/e2e-transitions");
    Sapphire::Data::ExdData data;
    if(!data.init(argv[1])) throw std::runtime_error("cannot initialize game data");
    Json result{{"profile", "sapphire-3.3"}, {"version", 1}, {"territory", 130}, {"exits", Json::array()}};
    result["ignored_optional_layers"] = Json::array();
    std::map<uint16_t, Json> targets;
    for(auto entry : objects(data, 130, result["ignored_optional_layers"]))
    {
      if(entry["kind"] != "exit") continue;
      const auto target = entry["target_territory"].get<uint16_t>();
      if(target)
      {
        if(!targets.count(target)) targets[target] = objects(data, target, result["ignored_optional_layers"]);
        Json matches = Json::array();
        for(const auto& candidate : targets[target])
          if(candidate["kind"] == "pop" && candidate["id"] == entry["target_pop"])
            matches.push_back(candidate);
        entry["destinations"] = matches;
      }
      result["exits"].push_back(std::move(entry));
    }
    if(argc == 5)
    {
      const auto id = std::stoul(argv[4]);
      Json matches = Json::array();
      for(const auto& exit : result["exits"])
        if(exit["id"] == id) matches.push_back(exit);
      if(matches.size() != 1) throw std::runtime_error("exit must resolve exactly once in territory 130");
      const auto exit = matches[0];
      if(!exit["enabled"].get<bool>() || exit["shape"] != 1 || exit["exit_type"] != 1 ||
         exit.value("destinations", Json::array()).size() != 1)
        throw std::runtime_error("only enabled ordinary box exits with one destination are supported");
      const auto rotation = exit["rotation"].get<Sapphire::Testing::Point>();
      const auto scale = exit["scale"].get<Sapphire::Testing::Point>();
      if(std::abs(rotation[0]) > 0.0001f || std::abs(rotation[2]) > 0.0001f ||
         scale[0] <= 0 || scale[0] > 30 || scale[1] <= 0 || scale[2] <= 0)
        throw std::runtime_error("unsupported exit transform");
      auto center = exit["position"].get<Sapphire::Testing::Point>();
      auto start = center;
      // Start outside even the full-scale circumscribed box, independent of yaw.
      const auto approachDistance = std::hypot(scale[0], scale[2]) + 2;
      start[0] -= std::cos(rotation[1]) * approachDistance;
      start[2] += std::sin(rotation[1]) * approachDistance;
      Sapphire::Common::Navi::NaviProvider finder("w1t1");
      if(!finder.init(argv[2])) throw std::runtime_error("source navigation mesh unavailable");
      dtNavMeshQuery query;
      if(dtStatusFailed(query.init(finder.getNavMesh(), 4096))) throw std::runtime_error("navigation query unavailable");
      dtQueryFilter filter; filter.setIncludeFlags(0xffff);
      auto surface = [&](const Sapphire::Testing::Point& point, const Sapphire::Testing::Point& extents) {
        dtPolyRef ref = 0; Sapphire::Testing::Point nearest{};
        auto status = query.findNearestPoly(point.data(), extents.data(), &filter, &ref, nearest.data());
        if(dtStatusFailed(status) || !ref) throw std::runtime_error("no walkable surface in selected exit approach");
        return nearest;
      };
      // A box center is not necessarily foot height. Project onto existing ground,
      // and require the result inside a conservative rotation-independent inner volume.
      const auto radius = std::min(scale[0], scale[2]) * 0.5f;
      auto destination = surface(center, {radius, scale[1] * 0.5f, radius});
      if(std::hypot(destination[0]-center[0], destination[2]-center[2]) > radius ||
         std::abs(destination[1]-center[1]) > scale[1] * 0.5f)
        throw std::runtime_error("walkable endpoint is outside conservative exit volume");
      start = surface(start, {1, 8, 1});
      if(std::hypot(start[0]-center[0], start[2]-center[2]) <= std::hypot(scale[0], scale[2]))
        throw std::runtime_error("approach does not begin outside exit volume");
      auto route = Sapphire::Testing::navigationRoute(*finder.getNavMesh(), start, destination);
      double length = 0;
      for(size_t i = 1; i < route.size(); ++i)
      {
        double squared = 0;
        for(size_t axis = 0; axis < 3; ++axis) squared += std::pow(route[i][axis] - route[i-1][axis], 2);
        length += std::sqrt(squared);
      }
      const auto targetTerritory = exit["target_territory"].get<uint16_t>();
      const auto arrival = exit["destinations"][0]["position"].get<Sapphire::Testing::Point>();
      Json discoveryMatches = Json::array();
      for(const auto& candidate : targets.at(targetTerritory))
      {
        if(candidate["kind"] != "map_range" || !candidate.value("enabled", false) ||
           !candidate.value("discovery_enabled", false) || candidate.value("shape", 0) != 3)
          continue;
        const auto c = candidate["position"].get<Sapphire::Testing::Point>();
        const auto s = candidate["scale"].get<Sapphire::Testing::Point>();
        if(s[0] <= 0 || s[1] <= 0 || s[2] <= 0) continue;
        const auto horizontal = std::hypot(arrival[0]-c[0], arrival[2]-c[2]);
        if(horizontal <= std::min(s[0], s[2]) * 0.5f &&
           std::abs(arrival[1]-c[1]) <= s[1] * 0.5f)
          discoveryMatches.push_back(candidate);
      }
      if(discoveryMatches.size() != 1)
        throw std::runtime_error("arrival must resolve exactly one enabled spherical discovery range");
      auto territoryInfo = data.getRow<Excel::TerritoryType>(targetTerritory);
      auto mapInfo = territoryInfo ? data.getRow<Excel::Map>(territoryInfo->data().Map) : nullptr;
      if(!territoryInfo || !mapInfo) throw std::runtime_error("discovery map metadata unavailable");
      auto discovery = discoveryMatches[0];
      discovery["map_id"] = territoryInfo->data().Map;
      discovery["map_discovery_index"] = mapInfo->data().DiscoveryIndex;
      discovery["uint16_storage"] = mapInfo->data().IsUint16Discovery != 0;
      result.erase("exits");
      result["transition"] = exit;
      result["supported_discovery"] = discovery;
      result["route"] = route; result["route_length"] = length;
      result["navigation"] = {{"mesh", std::filesystem::absolute(std::filesystem::path(argv[2]) / "w1t1" / "w1t1.nav").generic_string()},
                               {"format", "TSET-v1"}, {"polyref_bits", sizeof(dtPolyRef) * 8}};
    }
    std::ofstream output(argv[argc == 5 ? 3 : 2]);
    output << result.dump(2) << '\n';
    if(!output) throw std::runtime_error("cannot write transition metadata");
    return 0;
  }
  catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
