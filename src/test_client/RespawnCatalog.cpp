// Read-only source binding for the narrow defeated-player homepoint return scenario.
#include <Exd/ExdData.h>
#include <Logging/Logger.h>
#include <GameData.h>
#include <File.h>
#include <datReader/DatCategories/bg/lgb.h>
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>

using Json = nlohmann::json;

int main(int argc, char** argv)
{
  if(argc != 3)
  {
    std::cerr << "Usage: sapphire_test_respawn_catalog <game/sqpack> <output.json>\n";
    return 2;
  }
  try
  {
    Sapphire::Logger::init("log/e2e-respawn-catalog");
    Sapphire::Data::ExdData data;
    if(!data.init(argv[1])) throw std::runtime_error("cannot initialize game data");
    constexpr uint32_t homepoint = 9;
    auto aetheryte = data.getRow<Excel::Aetheryte>(homepoint);
    if(!aetheryte) throw std::runtime_error("supported homepoint metadata missing");
    const auto territory = aetheryte->data().TerritoryType;
    const auto popRange = aetheryte->data().PopRange[0];
    if(territory != 130 || !popRange) throw std::runtime_error("unsupported homepoint destination");
    auto territoryRow = data.getRow<Excel::TerritoryType>(territory);
    if(!territoryRow) throw std::runtime_error("homepoint territory metadata missing");
    auto path = territoryRow->getString(territoryRow->data().LVB);
    const auto level = path.find("/level/");
    if(level == std::string::npos) throw std::runtime_error("homepoint territory has no level path");
    path = "bg/" + path.substr(0, level) + "/level/";

    Json matches = Json::array();
    LGB_GROUP::AssetTypeFilter filter = [](eAssetType type) { return type == eAssetType::PopRange; };
    for(const auto* name : {"bg", "planmap", "planevent"})
    {
      const auto filePath = path + name + ".lgb";
      if(!data.getGameData()->doesFileExist(filePath))
        throw std::runtime_error("missing required homepoint level layer: " + filePath);
      auto file = data.getGameData()->getFile(filePath);
      auto section = file->access_data_sections().at(0);
      if(section.size() < sizeof(LGB_FILE_HEADER) || std::memcmp(section.data(), "LGB1", 4) ||
         std::memcmp(section.data() + 12, "LGP1", 4))
        throw std::runtime_error("unsupported homepoint level section: " + filePath);
      LGB_FILE lgb(section.data(), name, &filter);
      for(const auto& group : lgb.groups)
        for(const auto& entry : group.entries)
          if(entry->header.InstanceID == popRange)
          {
            const auto& transform = entry->header.Transformation;
            matches.push_back({{"id", popRange}, {"position", {transform.Translation.x,
              transform.Translation.y, transform.Translation.z}}, {"rotation", {transform.Rotation.x,
              transform.Rotation.y, transform.Rotation.z}}});
          }
    }
    if(matches.size() != 1) throw std::runtime_error("homepoint pop range must resolve exactly once");
    Json output{{"version", 1}, {"profile", "sapphire-3.3"}, {"homepoint", homepoint},
      {"territory", territory}, {"pop_range", matches[0]}};
    std::ofstream file(argv[2]);
    if(!file || !(file << output.dump(2) << '\n')) throw std::runtime_error("cannot write respawn catalog");
  }
  catch(const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
