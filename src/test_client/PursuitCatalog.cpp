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

    constexpr uint32_t proximityLayout = 3746983;
    nlohmann::json proximitySpawn;
    for(const auto& [groupId, group] : population.items())
      if(group.contains("bnpcs") && group["bnpcs"].contains(std::to_string(proximityLayout)))
        proximitySpawn = group["bnpcs"][std::to_string(proximityLayout)];
    if(proximitySpawn.is_null() || proximitySpawn["baseInfo"]["baseId"] != 735 ||
       proximitySpawn["baseInfo"]["level"] != 6 ||
       proximitySpawn["baseInfo"]["activeType"] != 0 ||
       proximitySpawn["popInfo"]["nonpop"] != 0 ||
       proximitySpawn["popInfo"]["invalidRepop"] != 0 ||
       proximitySpawn["SenseInfo"]["Sense"] != nlohmann::json::array({1, 0}) ||
       proximitySpawn["SenseInfo"]["SenseRange"] != nlohmann::json::array({14, 10}) ||
       proximitySpawn["Behaviour"]["wanderingRange"] != 6)
      throw std::runtime_error("supported active vision population binding missing");
    const auto proximityOrigin = proximitySpawn["baseInfo"]["position"].get<Sapphire::Testing::Point>();
    const auto proximityRotation = proximitySpawn["baseInfo"]["rotation"].get<float>();
    constexpr double pi = 3.14159265358979323846;
    auto radial = [&](double angle, double distance)
    {
      auto point = proximityOrigin;
      point[0] += static_cast<float>(std::sin(angle) * distance);
      point[2] += static_cast<float>(std::cos(angle) * distance);
      return point;
    };
    auto appendRoute = [&](std::vector<Sapphire::Testing::Point>& combined,
                           const Sapphire::Testing::Point& from,
                           const Sapphire::Testing::Point& to)
    {
      std::vector<Sapphire::Testing::Point> segment;
      try { segment = Sapphire::Testing::navigationRoute(*finder.getNavMesh(), from, to); }
      catch(const std::exception& error)
      { throw std::runtime_error("active-vision segment unavailable: " + std::string(error.what())); }
      if(!combined.empty() && !segment.empty()) segment.erase(segment.begin());
      combined.insert(combined.end(), segment.begin(), segment.end());
    };
    std::vector<Sapphire::Testing::Point> proximityRoute;
    auto proximityStart = radial(proximityRotation, 20.0);
    auto previous = proximityStart;
    for(size_t index = 0; index < 9; ++index)
    {
      const auto angle = proximityRotation + static_cast<double>(index) * pi / 4.0;
      const auto next = radial(angle, 3.0);
      appendRoute(proximityRoute, previous, next);
      previous = next;
    }
    double proximityLength = 0;
    for(size_t i = 1; i < proximityRoute.size(); ++i)
      proximityLength += std::sqrt(std::pow(proximityRoute[i][0]-proximityRoute[i-1][0],2) +
                                   std::pow(proximityRoute[i][1]-proximityRoute[i-1][1],2) +
                                   std::pow(proximityRoute[i][2]-proximityRoute[i-1][2],2));
    if(proximityRoute.empty() || proximityLength < 20 || proximityLength > 80 ||
       std::hypot(proximityRoute.front()[0]-proximityOrigin[0],
                  proximityRoute.front()[2]-proximityOrigin[2]) < 15)
      throw std::runtime_error("no complete bounded active-vision approach route");
    std::vector<Sapphire::Testing::Point> proximityEscape;
    double proximityEscapeLength = std::numeric_limits<double>::infinity();
    for(size_t index = 0; index < 16; ++index)
    {
      try
      {
        const auto angle = proximityRotation + static_cast<double>(index) * pi / 8.0;
        auto candidate = Sapphire::Testing::navigationRoute(
            *finder.getNavMesh(), proximityRoute.back(), radial(angle, 50.0));
        double length = 0;
        for(size_t i = 1; i < candidate.size(); ++i)
          length += std::sqrt(std::pow(candidate[i][0]-candidate[i-1][0],2) +
                             std::pow(candidate[i][1]-candidate[i-1][1],2) +
                             std::pow(candidate[i][2]-candidate[i-1][2],2));
        const auto displacement = std::hypot(candidate.back()[0]-proximityOrigin[0],
                                              candidate.back()[2]-proximityOrigin[2]);
        if(displacement >= 45 && displacement <= 60 && length <= 80 &&
           length < proximityEscapeLength)
        { proximityEscape = std::move(candidate); proximityEscapeLength = length; }
      }
      catch(const std::exception&) { }
    }
    if(proximityEscape.empty())
      throw std::runtime_error("no complete bounded active-vision escape route");
    Sapphire::Testing::Point witnessPosition{};
    bool haveWitness = false;
    for(size_t index = 0; index < 16 && !haveWitness; ++index)
    {
      try
      {
        const auto angle = proximityRotation + static_cast<double>(index) * pi / 8.0;
        auto witnessRoute = Sapphire::Testing::navigationRoute(
            *finder.getNavMesh(), proximityOrigin, radial(angle, 30.0));
        const auto candidate = witnessRoute.back();
        const auto witnessDistance = std::hypot(candidate[0]-proximityOrigin[0],
                                                candidate[2]-proximityOrigin[2]);
        const auto fixtureSeparation = std::hypot(candidate[0]-proximityRoute.front()[0],
                                                  candidate[2]-proximityRoute.front()[2]);
        if(witnessDistance >= 25 && witnessDistance <= 35 && fixtureSeparation >= 5)
        { witnessPosition = candidate; haveWitness = true; }
      }
      catch(const std::exception&) { }
    }
    if(!haveWitness) throw std::runtime_error("no bounded active-vision witness position");

    nlohmann::json output{{"version",2},{"profile","sapphire-3.3"},{"territory",141},
      {"enemy",{{"layout_id",layout},{"base_id",302},{"level",14},{"position",origin}}},
      {"route",best},{"route_length",bestLength},
      {"leash_route",leash},{"leash_route_length",leashLength},
      {"proximity_enemy",{{"layout_id",proximityLayout},{"base_id",735},{"level",6},
                           {"position",proximityOrigin},{"rotation",proximityRotation},
                           {"active_type",0},{"sense",1},{"sense_range",14},
                           {"wandering_range",6},{"level_adjusted_range",14.0-std::pow(1.53,3.0)}}},
      {"proximity_route",proximityRoute},{"proximity_route_length",proximityLength},
      {"proximity_escape_route",proximityEscape},
      {"proximity_escape_route_length",proximityEscapeLength},
      {"proximity_witness_position",witnessPosition},
      {"navigation",{{"mesh",std::filesystem::absolute(std::filesystem::path(argv[1])/"w1f2"/"w1f2.nav").generic_string()},
                     {"format","TSET-v1"},{"polyref_bits",sizeof(dtPolyRef)*8}}}};
    std::ofstream file(argv[3]);
    if(!file || !(file << output.dump(2) << '\n')) throw std::runtime_error("cannot write pursuit catalog");
  }
  catch(const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
