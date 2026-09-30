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
      if(actionId != 3 && actionId != 6 && actionId != 9 && actionId != 11 && actionId != 53 && actionId != 54 && actionId != 142)
        throw std::runtime_error("action is not an enabled audited combat action");
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
    if(argc == 3)
    {
      output["sprint"] = metadata(3);
      output["return"] = metadata(6);
      output["bootshine"] = metadata(53);
      output["true_strike"] = metadata(54);
      output["blizzard"] = metadata(142);
      auto combo = metadata(11);
      uint32_t requiredExp = 0;
      for(uint32_t level = 1; level < combo["level"].get<uint32_t>(); ++level)
      {
        auto growth = data.getRow<Excel::ParamGrow>(level);
        if(!growth || !growth->data().NextExp)
          throw std::runtime_error("combo prerequisite EXP metadata missing");
        requiredExp += growth->data().NextExp;
      }
      auto levelOne = data.getRow<Excel::ParamGrow>(1);
      if(!levelOne || !levelOne->data().BaseExp)
        throw std::runtime_error("level-one enemy EXP metadata missing");
      combo["required_cumulative_exp"] = requiredExp;
      combo["level_one_enemy_exp"] = levelOne->data().BaseExp;
      combo["minimum_level_one_defeats"] =
        (requiredExp + levelOne->data().BaseExp - 1) / levelOne->data().BaseExp;
      auto levelFourteen = data.getRow<Excel::ParamGrow>(14);
      if(!levelFourteen || !levelFourteen->data().BaseExp)
        throw std::runtime_error("level-fourteen enemy EXP metadata missing");
      combo["level_fourteen_enemy_exp"] = levelFourteen->data().BaseExp;
      combo["minimum_level_fourteen_defeats"] =
        (requiredExp + levelFourteen->data().BaseExp - 1) / levelFourteen->data().BaseExp;
      output["first_fast_blade_combo"] = combo;
      output["representative_high_level_enemy"] =
        {{"level", 14}, {"base_exp", levelFourteen->data().BaseExp}};
    }
    std::ofstream file(argv[2]);
    if(!file || !(file << output.dump(2) << '\n')) throw std::runtime_error("cannot write combat catalog");
  }
  catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
