// Read-only binding for the supported part of Coming to Ul'dah (66130).
#include <Exd/ExdData.h>
#include <Logging/Logger.h>
#include <Navi/NaviProvider.h>
#include <File.h>
#include <datReader/DatCategories/bg/lgb.h>
#include <nlohmann/json.hpp>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cmath>
#include <set>
#include <map>
#include <algorithm>
#include "NavigationRoute.h"

using Json = nlohmann::json;

// Closed exits of the opening and the pop ranges the script returns the player to.
static const std::map<uint32_t, uint32_t> kReturnPositions{
  {4101537, 4101685}, {4101525, 4101680}, {4101535, 4101681}, {4101587, 4101691}};

static void openingRanges(Sapphire::Data::ExdData& data, Json& ranges, Json& returns)
{
  const std::set<uint32_t> supported{4101537, 4101525, 4101535, 4101587};
  std::set<uint32_t> returnIds;
  for(const auto& [range, pop] : kReturnPositions) returnIds.insert(pop);
  auto territory = data.getRow<Excel::TerritoryType>(182);
  if(!territory) throw std::runtime_error("opening territory metadata missing");
  auto path = territory->getString(territory->data().LVB);
  const auto level = path.find("/level/");
  if(level == std::string::npos) throw std::runtime_error("opening territory has no level path");
  path = "bg/" + path.substr(0, level) + "/level/";
  ranges = Json::array();
  returns = Json::object();
  // The return spots are Level rows, not layout pop ranges.
  for(const auto id : returnIds)
  {
    auto level = data.getRow<Excel::Level>(id);
    if(!level || level->data().TerritoryType != 182)
      throw std::runtime_error("opening return position " + std::to_string(id) + " is not a Level row of 182");
    returns[std::to_string(id)] = {{"position",{level->data().TransX,level->data().TransY,level->data().TransZ}},
                                   {"rotation",level->data().RotY}};
  }
  LGB_GROUP::AssetTypeFilter filter = [](eAssetType type) { return type == eAssetType::EventRange; };
  for(const auto* name : {"bg", "planmap", "planevent", "planner"})
  {
    const auto filePath = path + name + ".lgb";
    if(!data.getGameData()->doesFileExist(filePath))
    {
      if(std::string(name) == "planner") continue;
      throw std::runtime_error("missing opening level layer: " + filePath);
    }
    auto section = data.getGameData()->getFile(filePath)->access_data_sections().at(0);
    if(section.size() < sizeof(LGB_FILE_HEADER) || std::memcmp(section.data(), "LGB1", 4) ||
       std::memcmp(section.data() + 12, "LGP1", 4))
    {
      if(std::string(name) == "planner") continue;
      throw std::runtime_error("unsupported opening level layer: " + filePath);
    }
    LGB_FILE lgb(section.data(), name, &filter);
    for(const auto& group : lgb.groups)
      for(const auto& entry : group.entries)
      {
        const auto& header = entry->header;
        if(!supported.count(header.InstanceID)) continue;
        const auto& range = std::static_pointer_cast<EventRangeEntry>(entry)->header;
        ranges.push_back({{"id",header.InstanceID},
                          {"position",{header.Transformation.Translation.x,header.Transformation.Translation.y,
                                       header.Transformation.Translation.z}},
                          {"rotation",{header.Transformation.Rotation.x,header.Transformation.Rotation.y,
                                       header.Transformation.Rotation.z}},
                          {"scale",{header.Transformation.Scale.x,header.Transformation.Scale.y,
                                    header.Transformation.Scale.z}},
                          {"enabled",range.triggerBox.enabled != 0},
                          {"shape",static_cast<int>(range.triggerBox.triggerBoxShape)}});
      }
  }
  if(ranges.size() != supported.size())
    throw std::runtime_error("source-defined opening event ranges did not resolve exactly");
  for(auto& row : ranges)
    row["return_position"] = returns.at(std::to_string(kReturnPositions.at(row.at("id").get<uint32_t>())))
                               .at("position");
}

int main(int argc, char** argv)
{
  if(argc != 4)
  {
    std::cerr << "Usage: sapphire_test_opening_quest_catalog <game/sqpack> <mesh-root> <output.json>\n";
    return 2;
  }
  try
  {
    Sapphire::Logger::init("log/e2e-opening-quest-catalog");
    Sapphire::Data::ExdData data;
    if(!data.init(argv[1])) throw std::runtime_error("cannot initialize game data");
    auto quest = data.getRow<Excel::Quest>(66130);
    auto giverRow = data.getRow<Excel::Level>(3969639);
    auto recipientRow = data.getRow<Excel::Level>(3969632);
    if(!quest || !giverRow || !recipientRow || quest->data().Client != 1003987 ||
       quest->data().Finish != 1003988 || giverRow->data().BaseId != 1003987 ||
       recipientRow->data().BaseId != 1003988 || giverRow->data().TerritoryType != 182 ||
       recipientRow->data().TerritoryType != 182)
      throw std::runtime_error("Coming to Ul'dah source binding missing");
    auto growth = data.getRow<Excel::ParamGrow>(quest->data().ClassLevel);
    if(!growth) throw std::runtime_error("Coming to Ul'dah level data missing");
    const auto exp = (quest->data().Reward.ExpBonus * growth->data().BaseExp *
                      growth->data().EventExpRate) / 100;
    const Sapphire::Testing::Point start{42.0f, 4.0f, -157.6f};
    const Sapphire::Testing::Point giver{giverRow->data().TransX, giverRow->data().TransY, giverRow->data().TransZ};
    const Sapphire::Testing::Point recipient{recipientRow->data().TransX, recipientRow->data().TransY,
                                              recipientRow->data().TransZ};
    Sapphire::Common::Navi::NaviProvider finder("w1t1");
    if(!finder.init(argv[2])) throw std::runtime_error("Ul'dah tile-cache navmesh unavailable");
    Json ranges, returns;
    openingRanges(data, ranges, returns);
    const auto selected = std::find_if(ranges.begin(), ranges.end(),
      [](const auto& range) { return range.at("id") == 4101537; });
    if(selected == ranges.end() || selected->at("shape") != 1)
      throw std::runtime_error("supported opening range is not a source-defined box");
    const auto rangeCenter = selected->at("position").get<Sapphire::Testing::Point>();
    auto rangeRoute = Sapphire::Testing::navigationRoute(*finder.getNavMesh(), start, rangeCenter);
    const auto endpoint = rangeRoute.back();
    const auto scale = selected->at("scale").get<Sapphire::Testing::Point>();
    const auto rotation = selected->at("rotation").get<Sapphire::Testing::Point>();
    const auto dx = endpoint[0] - rangeCenter[0], dz = endpoint[2] - rangeCenter[2];
    const auto localX = std::cos(rotation[1]) * dx - std::sin(rotation[1]) * dz;
    const auto localZ = std::sin(rotation[1]) * dx + std::cos(rotation[1]) * dz;
    if(std::abs(localX) > scale[0] * 0.5f || std::abs(localZ) > scale[2] * 0.5f ||
       std::abs(endpoint[1] - rangeCenter[1]) > scale[1] * 0.5f)
      throw std::runtime_error("opening range route does not end inside the source box");
    auto approach = Sapphire::Testing::navigationRoute(*finder.getNavMesh(), start, giver);
    auto length = [](const auto& route)
    {
      double result = 0;
      for(size_t i = 1; i < route.size(); ++i)
        result += std::sqrt(std::pow(route[i][0]-route[i-1][0],2) +
                           std::pow(route[i][1]-route[i-1][1],2) +
                           std::pow(route[i][2]-route[i-1][2],2));
      return result;
    };
    Json starterRings = Json::array();
    for(const auto itemId : {4423u, 4424u, 4425u, 4426u})
    {
      auto item = data.getRow<Excel::Item>(itemId);
      if(!item || item->data().Slot != 12 || item->data().StackMax != 1)
        throw std::runtime_error("opening ring source equipment binding missing");
      starterRings.push_back({{"item",itemId},{"equip_slot_category",item->data().Slot},
                              {"stack_max",item->data().StackMax}});
    }
    bool completionRoute = true;
    std::vector<Sapphire::Testing::Point> finish;
    try { finish = Sapphire::Testing::navigationRoute(*finder.getNavMesh(), giver, recipient); }
    catch(const std::exception&) { completionRoute = false; }
    nlohmann::json output{{"version",1},{"profile","sapphire-3.3"},{"territory",182},
      {"quest",66130},{"giver",{{"layout_id",3969639},{"base_id",1003987},{"position",giver}}},
      {"recipient",{{"layout_id",3969632},{"base_id",1003988},{"position",recipient}}},
      {"reward",{{"exp",exp},{"gil",quest->data().Reward.Gil}}},
      {"approach_route",approach},{"approach_route_length",length(approach)},
      {"completion_route_supported",completionRoute},{"opening_event_ranges",ranges},
      {"starter_ring_items",starterRings},
      {"supported_range",{{"event_id",1245187},{"param",4101537},{"route",rangeRoute},
                           {"route_length",length(rangeRoute)},{"expected_scene",20},
                           {"return_position",selected->at("return_position")}}},
      // Leaving the arrival area while Wymond still has to be spoken to (opening sequence 1).
      {"closed_arrival_area",{{"event_id",1245187},{"param",4101587},{"expected_scene",20},
                              {"return_position",returns.at("4101691").at("position")}}},
      {"return_positions",returns},
      {"navigation",{{"mesh",std::filesystem::absolute(std::filesystem::path(argv[2])/"w1t1"/"w1t1.nav").generic_string()},
                     {"format","TSET-v1"},{"polyref_bits",sizeof(dtPolyRef)*8}}}};
    if(completionRoute)
    {
      output["completion_route"] = finish;
      output["completion_route_length"] = length(finish);
    }
    else output["completion_route_blocker"] = "incomplete navigation corridor";
    std::ofstream file(argv[3]);
    if(!file || !(file << output.dump(2) << '\n')) throw std::runtime_error("cannot write opening quest catalog");
  }
  catch(const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
