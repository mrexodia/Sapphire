// Read-only binding for the supported part of Coming to Ul'dah (66130).
#include <Exd/ExdData.h>
#include <Logging/Logger.h>
#include <Navi/NaviProvider.h>
#include <nlohmann/json.hpp>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cmath>
#include "NavigationRoute.h"

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
    bool completionRoute = true;
    std::vector<Sapphire::Testing::Point> finish;
    try { finish = Sapphire::Testing::navigationRoute(*finder.getNavMesh(), giver, recipient); }
    catch(const std::exception&) { completionRoute = false; }
    nlohmann::json output{{"version",1},{"profile","sapphire-3.3"},{"territory",182},
      {"quest",66130},{"giver",{{"layout_id",3969639},{"base_id",1003987},{"position",giver}}},
      {"recipient",{{"layout_id",3969632},{"base_id",1003988},{"position",recipient}}},
      {"reward",{{"exp",exp},{"gil",quest->data().Reward.Gil}}},
      {"approach_route",approach},{"approach_route_length",length(approach)},
      {"completion_route_supported",completionRoute},
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
