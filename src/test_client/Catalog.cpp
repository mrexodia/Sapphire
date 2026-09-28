// Optional local-data inspection tool. Does not connect to Sapphire or mutate game state.
#include <Exd/ExdData.h>
#include <Logging/Logger.h>
#include <nlohmann/json.hpp>
#include <iostream>
#include <fstream>
#include <filesystem>
#include <Navi/NaviProvider.h>
#include <cmath>
#include "NavigationRoute.h"

int main(int argc, char** argv)
{
  if(argc != 2 && argc != 3 && argc != 4 && argc != 5)
  {
    std::cerr << "Usage: sapphire_test_catalog <matching game/sqpack> [quest-id | <mesh root> <output.json> [quest-id]]\n";
    return 2;
  }
  try
  {
    Sapphire::Logger::init("log/e2e-catalog");
    Sapphire::Data::ExdData data;
    if(!data.init(argv[1])) throw std::runtime_error("cannot initialize game data");
    const uint32_t questId = argc == 5 ? static_cast<uint32_t>(std::stoul(argv[4]))
                                        : (argc == 3 ? static_cast<uint32_t>(std::stoul(argv[2])) : 65685);
    auto quest = data.getRow<Excel::Quest>(questId);
    if(!quest) throw std::runtime_error("quest missing from game data");
    const auto& q = quest->data();
    nlohmann::json output = {{"profile", "sapphire-3.3"}, {"quest", questId},
      {"level", q.ClassLevel}, {"previous_quests", q.PrevQuest}, {"gil", q.Reward.Gil},
      {"client", q.Client}, {"finish", q.Finish}, {"actors", nlohmann::json::array()}};
    auto growth = data.getRow<Excel::ParamGrow>(q.ClassLevel);
    if(!growth) throw std::runtime_error("quest level data missing");
    output["exp"] = (q.Reward.ExpBonus * growth->data().BaseExp * growth->data().EventExpRate) / 100;
    auto startingClass = data.getRow<Excel::ClassJob>(1);
    if(!startingClass) throw std::runtime_error("starter class data missing");
    output["class_job"] = 1;
    output["work_index"] = startingClass->data().WorkIndex;
    output["items"] = nlohmann::json::array();
    output["optional_items"] = nlohmann::json::array();
    for(size_t i = 0; i < 6; ++i)
      if(q.Reward.Item[i]) output["items"].push_back({{"id", q.Reward.Item[i]}, {"count", q.Reward.ItemNum[i]}});
    for(size_t i = 0; i < 5; ++i)
      if(q.Reward.OptionalItem[i]) output["optional_items"].push_back({{"id", q.Reward.OptionalItem[i]}, {"count", q.Reward.OptionalItemNum[i]}});
    for(auto id : data.getIdList<Excel::Level>())
    {
      auto row = data.getRow<Excel::Level>(id);
      if(!row || (row->data().BaseId != q.Client && row->data().BaseId != q.Finish)) continue;
      const auto& p = row->data();
      output["actors"].push_back({{"layout_id", id}, {"base_id", p.BaseId}, {"territory", p.TerritoryType},
        {"position", {p.TransX, p.TransY, p.TransZ}}, {"event_handler", p.EventHandler}});
    }
    if(argc >= 4)
    {
      // Use the same current tile-cache format as the server, not legacy MSET files.
      Sapphire::Common::Navi::NaviProvider finder("w1t1");
      if(!finder.init(argv[2])) throw std::runtime_error("Ul'dah tile-cache navmesh unavailable");
      Sapphire::Common::Vector3 start{}, finish{};
      bool haveStart = false, haveFinish = false;
      for(const auto& actor : output["actors"])
      {
        if(actor["territory"] != 130) continue;
        Sapphire::Common::Vector3 p{actor["position"][0], actor["position"][1], actor["position"][2]};
        if(actor["base_id"] == q.Client) { start = p; haveStart = true; }
        if(actor["base_id"] == q.Finish) { finish = p; haveFinish = true; }
      }
      if(!haveStart || !haveFinish) throw std::runtime_error("quest actors missing from territory 130");
      auto path = Sapphire::Testing::navigationRoute(*finder.getNavMesh(),
        {start.x, start.y, start.z}, {finish.x, finish.y, finish.z});
      auto distance = [](const auto& a, const auto& b) {
        return std::sqrt(std::pow(a[0]-b[0], 2) + std::pow(a[1]-b[1], 2) + std::pow(a[2]-b[2], 2));
      };
      double length = 0;
      for(size_t i = 1; i < path.size(); ++i)
      {
        const auto step = distance(path[i-1], path[i]);
        if(!std::isfinite(step) || step > 2) throw std::runtime_error("route contains an unsupported jump");
        length += step;
      }
      output["version"] = 1;
      output["navigation"] = {{"mesh", std::filesystem::absolute(std::filesystem::path(argv[2]) / "w1t1" / "w1t1.nav").generic_string()},
                               {"format", "TSET-v1"}, {"polyref_bits", sizeof(dtPolyRef) * 8}};
      output["route_length"] = length;
      output["route"] = nlohmann::json::array();
      for(const auto& point : path) output["route"].push_back(point);
      std::ofstream file(argv[3]);
      if(!file) throw std::runtime_error("cannot open output catalog");
      file << output.dump(2) << std::endl;
    }
    else std::cout << output.dump(2) << std::endl;
    return 0;
  }
  catch(const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
