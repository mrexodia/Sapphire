// Read-only action metadata for the intentionally narrow initial combat profile.
#include <Exd/ExdData.h>
#include <Logging/Logger.h>
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
int main(int argc, char** argv)
{
  if(argc != 3) { std::cerr << "Usage: sapphire_test_combat_catalog <game/sqpack> <output.json>\n"; return 2; }
  try
  {
    Sapphire::Logger::init("log/e2e-combat-catalog");
    Sapphire::Data::ExdData data;
    if(!data.init(argv[1])) throw std::runtime_error("cannot initialize game data");
    auto row = data.getRow<Excel::Action>(9);
    if(!row) throw std::runtime_error("Fast Blade action missing");
    const auto& a = row->data();
    auto growth = data.getRow<Excel::ParamGrow>(a.Level);
    if(!growth) throw std::runtime_error("action level data missing");
    auto classJob = data.getRow<Excel::ClassJob>(a.UseClassJob);
    if(!classJob) throw std::runtime_error("action class/job data missing");
    nlohmann::json output{{"version", 1}, {"profile", "sapphire-3.3"}, {"action", 9},
      {"class_job", a.UseClassJob}, {"work_index", classJob->data().WorkIndex},
      {"level", a.Level}, {"base_exp", growth->data().BaseExp}, {"category", a.Category},
      {"cost_type", a.CostType}, {"cost", a.CostValue}, {"range", a.SelectRange},
      {"cast_ms", a.CastTime * 100}, {"recast_ms", a.RecastTime * 100}, {"recast_group", a.RecastGroup},
      {"effect_type", a.EffectType}, {"target_enemy", bool(a.SelectEnemy)}};
    std::ofstream file(argv[2]);
    if(!file || !(file << output.dump(2) << '\n')) throw std::runtime_error("cannot write combat catalog");
  }
  catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
