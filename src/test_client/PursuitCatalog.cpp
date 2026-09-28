// Read-only binding for one short natural-enemy pursuit route.
#include <Logging/Logger.h>
#include <Navi/NaviProvider.h>
#include <nlohmann/json.hpp>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <cmath>
#include "NavigationRoute.h"

int main(int argc, char** argv)
{
  if(argc != 4)
  {
    std::cerr << "Usage: sapphire_test_pursuit_catalog <mesh-root> <w1f2-population.json> <output.json>\n";
    return 2;
  }
  try
  {
    Sapphire::Logger::init("log/e2e-pursuit-catalog");
    nlohmann::json population;
    std::ifstream input(argv[2]);
    if(!input || !(input >> population)) throw std::runtime_error("cannot read staged population");
    constexpr uint32_t layout = 3749193;
    nlohmann::json spawn;
    for(const auto& [groupId, group] : population.items())
      if(group.contains("bnpcs") && group["bnpcs"].contains(std::to_string(layout)))
        spawn = group["bnpcs"][std::to_string(layout)];
    if(spawn.is_null() || spawn["baseInfo"]["baseId"] != 302 ||
       spawn["baseInfo"]["level"] != 14 || spawn["popInfo"]["nonpop"] != 0)
      throw std::runtime_error("supported natural population binding missing");
    auto origin = spawn["baseInfo"]["position"].get<Sapphire::Testing::Point>();
    auto start = origin; start[0] += 1.0f;
    Sapphire::Common::Navi::NaviProvider finder("w1f2");
    if(!finder.init(argv[1])) throw std::runtime_error("Central Thanalan tile-cache navmesh unavailable");
    auto chooseRoute = [&](float requested, float minimumDisplacement, float maximumLength)
    {
      std::vector<Sapphire::Testing::Point> best;
      double bestLength = std::numeric_limits<double>::infinity();
      for(const auto delta : std::array<Sapphire::Testing::Point, 4>{{{requested,0,0},{-requested,0,0},
                                                                      {0,0,requested},{0,0,-requested}}})
      {
        auto end = start;
        for(size_t axis = 0; axis < 3; ++axis) end[axis] += delta[axis];
        try
        {
          auto route = Sapphire::Testing::navigationRoute(*finder.getNavMesh(), start, end);
          const auto displacement = std::hypot(route.back()[0]-origin[0], route.back()[2]-origin[2]);
          double length = 0;
          for(size_t i = 1; i < route.size(); ++i)
            length += std::sqrt(std::pow(route[i][0]-route[i-1][0],2) +
                               std::pow(route[i][1]-route[i-1][1],2) +
                               std::pow(route[i][2]-route[i-1][2],2));
          if(displacement >= minimumDisplacement && length <= maximumLength && length < bestLength)
          { best = std::move(route); bestLength = length; }
        }
        catch(const std::exception&) { }
      }
      if(best.empty()) throw std::runtime_error("no complete bounded pursuit/leash route");
      return std::make_pair(best, bestLength);
    };
    auto [best, bestLength] = chooseRoute(10, 8, 20);
    auto [leash, leashLength] = chooseRoute(50, 45, 70);
    nlohmann::json output{{"version",1},{"profile","sapphire-3.3"},{"territory",141},
      {"enemy",{{"layout_id",layout},{"base_id",302},{"level",14},{"position",origin}}},
      {"route",best},{"route_length",bestLength},
      {"leash_route",leash},{"leash_route_length",leashLength},
      {"navigation",{{"mesh",std::filesystem::absolute(std::filesystem::path(argv[1])/"w1f2"/"w1f2.nav").generic_string()},
                     {"format","TSET-v1"},{"polyref_bits",sizeof(dtPolyRef)*8}}}};
    std::ofstream file(argv[3]);
    if(!file || !(file << output.dump(2) << '\n')) throw std::runtime_error("cannot write pursuit catalog");
  }
  catch(const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
