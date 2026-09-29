// Read-only action metadata for intentionally narrow level-one combat profiles.
#include <Exd/ExdData.h>
#include <Logging/Logger.h>
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
int main(int argc, char** argv)
{
  if(argc != 3 && argc != 4) { std::cerr << "Usage: sapphire_test_combat_catalog <game/sqpack> <output.json> [action-id]\n"; return 2; }
  try
  {
    Sapphire::Logger::init("log/e2e-combat-catalog");
    Sapphire::Data::ExdData data;
    if(!data.init(argv[1])) throw std::runtime_error("cannot initialize game data");
    auto metadata = [&](uint32_t actionId)
    {
      if(actionId != 9 && actionId != 53 && actionId != 142)
        throw std::runtime_error("action is not an enabled starting-class ability");
      auto row = data.getRow<Excel::Action>(actionId);
      if(!row) throw std::runtime_error("starting-class action missing");
      const auto& a = row->data();
      auto growth = data.getRow<Excel::ParamGrow>(a.Level);
      auto classJob = data.getRow<Excel::ClassJob>(a.UseClassJob);
      if(!growth || !classJob) throw std::runtime_error("action class/level data missing");
      return nlohmann::json{{"action", actionId}, {"class_job", a.UseClassJob},
        {"work_index", classJob->data().WorkIndex}, {"level", a.Level},
        {"base_exp", growth->data().BaseExp}, {"category", a.Category},
        {"cost_type", a.CostType}, {"cost", a.CostValue}, {"range", a.SelectRange},
        {"cast_ms", a.CastTime * 100}, {"recast_ms", a.RecastTime * 100},
        {"recast_group", a.RecastGroup}, {"effect_type", a.EffectType},
        {"target_enemy", bool(a.SelectEnemy)}};
    };
    const uint32_t actionId = argc == 4 ? static_cast<uint32_t>(std::stoul(argv[3])) : 9;
    auto output = metadata(actionId);
    output["version"] = 1; output["profile"] = "sapphire-3.3";
    if(argc == 3) output["bootshine"] = metadata(53);
    std::ofstream file(argv[2]);
    if(!file || !(file << output.dump(2) << '\n')) throw std::runtime_error("cannot write combat catalog");
  }
  catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
