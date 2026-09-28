// Optional local-data inspection tool. Does not connect to Sapphire or mutate game state.
#include <Exd/ExdData.h>
#include <Logging/Logger.h>
#include <nlohmann/json.hpp>
#include <iostream>
#include <fstream>
#include <Navi/PathFinder.h>

int main(int argc, char** argv)
{
  if(argc != 2 && argc != 4)
  {
    std::cerr << "Usage: sapphire_test_catalog <matching game/sqpack> [<mesh root> <output.json>]\n";
    return 2;
  }
  try
  {
    Sapphire::Logger::init("log/e2e-catalog");
    Sapphire::Data::ExdData data;
    if(!data.init(argv[1])) throw std::runtime_error("cannot initialize game data");
    auto quest = data.getRow<Excel::Quest>(65685);
    if(!quest) throw std::runtime_error("Due Diligence missing from game data");
    const auto& q = quest->data();
    nlohmann::json output = {{"profile", "sapphire-3.3"}, {"quest", 65685},
      {"level", q.ClassLevel}, {"previous_quests", q.PrevQuest}, {"gil", q.Reward.Gil},
      {"client", q.Client}, {"finish", q.Finish}, {"actors", nlohmann::json::array()}};
    for(auto id : data.getIdList<Excel::Level>())
    {
      auto row = data.getRow<Excel::Level>(id);
      if(!row || (row->data().BaseId != 1001285 && row->data().BaseId != 1002278)) continue;
      const auto& p = row->data();
      output["actors"].push_back({{"layout_id", id}, {"base_id", p.BaseId}, {"territory", p.TerritoryType},
        {"position", {p.TransX, p.TransY, p.TransZ}}, {"event_handler", p.EventHandler}});
    }
    if(argc == 4)
    {
      using namespace Sapphire::Common::Navigation;
      PathFinder finder("w1t1");
      if(!finder.initialize(argv[2])) throw std::runtime_error("Ul'dah navmesh unavailable");
      Sapphire::Common::Vector3 start{}, finish{};
      bool haveStart = false, haveFinish = false;
      for(const auto& actor : output["actors"])
      {
        if(actor["territory"] != 130) continue;
        Sapphire::Common::Vector3 p{actor["position"][0], actor["position"][1], actor["position"][2]};
        if(actor["base_id"] == 1001285) { start = p; haveStart = true; }
        if(actor["base_id"] == 1002278) { finish = p; haveFinish = true; }
      }
      if(!haveStart || !haveFinish) throw std::runtime_error("quest actors missing from territory 130");
      auto path = finder.findPath({start, finish});
      if(path.result != PathfindingResult::Success || path.waypoints.empty())
        throw std::runtime_error("no supported navmesh route between quest actors");
      output["route"] = nlohmann::json::array();
      for(const auto& point : path.waypoints) output["route"].push_back({point.x, point.y, point.z});
      std::ofstream file(argv[3]);
      if(!file) throw std::runtime_error("cannot open output catalog");
      file << output.dump(2) << std::endl;
    }
    else std::cout << output.dump(2) << std::endl;
    return 0;
  }
  catch(const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
