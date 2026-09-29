// Read-only source binding for the narrow ordinary gil-shop sale scenario.
#include <Exd/ExdData.h>
#include <Logging/Logger.h>
#include <Navi/NaviProvider.h>
#include <nlohmann/json.hpp>
#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include "NavigationRoute.h"

int main(int argc, char** argv)
{
  if(argc != 4)
  {
    std::cerr << "Usage: sapphire_test_shop_catalog <game/sqpack> <mesh root> <output.json>\n";
    return 2;
  }
  try
  {
    Sapphire::Logger::init("log/e2e-shop-catalog");
    Sapphire::Data::ExdData data;
    if(!data.init(argv[1])) throw std::runtime_error("cannot initialize game data");
    auto reward = data.getRow<Excel::Item>(4551);
    if(!reward || !reward->data().Price) throw std::runtime_error("supported sale item has no gil value");
    Sapphire::Common::Navi::NaviProvider finder("w1t1");
    if(!finder.init(argv[2])) throw std::runtime_error("Ul'dah tile-cache navmesh unavailable");

    Sapphire::Common::Vector3 start{};
    bool haveStart = false;
    struct Candidate { uint32_t layout, base, event; Sapphire::Common::Vector3 position; };
    std::vector<Candidate> candidates;
    for(auto id : data.getIdList<Excel::Level>())
    {
      auto row = data.getRow<Excel::Level>(id);
      if(!row || row->data().TerritoryType != 130) continue;
      const auto& level = row->data();
      if(level.BaseId == 1001289)
      {
        start = {level.TransX, level.TransY, level.TransZ};
        haveStart = true;
      }
      auto npc = data.getRow<Excel::ENpcBase>(level.BaseId);
      if(!npc) continue;
      for(const auto& handler : npc->data().EventHandler)
        if((handler.EventHandler >> 16) == 4)
          candidates.push_back({id, level.BaseId, handler.EventHandler,
                                {level.TransX, level.TransY, level.TransZ}});
    }
    if(!haveStart || candidates.empty()) throw std::runtime_error("supported quest endpoint/shop actors missing");

    std::vector<std::array<float, 3>> best;
    Candidate selected{};
    double bestLength = std::numeric_limits<double>::infinity();
    for(const auto& candidate : candidates)
    {
      try
      {
        auto route = Sapphire::Testing::navigationRoute(*finder.getNavMesh(),
          {start.x, start.y, start.z}, {candidate.position.x, candidate.position.y, candidate.position.z});
        double length = 0;
        for(size_t i = 1; i < route.size(); ++i)
        {
          const auto& a = route[i - 1]; const auto& b = route[i];
          const double step = std::sqrt(std::pow(a[0]-b[0], 2) + std::pow(a[1]-b[1], 2) + std::pow(a[2]-b[2], 2));
          if(!std::isfinite(step) || step > 2) throw std::runtime_error("shop route contains unsupported jump");
          length += step;
        }
        if(length < bestLength || (length == bestLength && candidate.event < selected.event))
        {
          bestLength = length; best = std::move(route); selected = candidate;
        }
      }
      catch(const std::exception&) { /* A partial corridor is never selected. */ }
    }
    if(best.empty() || !std::isfinite(bestLength) || bestLength > 500)
      throw std::runtime_error("no complete bounded route to a gil shop");
    auto shop = data.getRow<Excel::Shop>(selected.event);
    if(!shop) throw std::runtime_error("selected gil shop has no source item list");
    uint32_t purchaseItem = 0, purchasePrice = std::numeric_limits<uint32_t>::max(), purchaseIndex = 0;
    for(uint32_t index = 0; index < 40; ++index)
    {
      const auto shopItemId = shop->data().Item[index];
      auto shopItem = data.getRow<Excel::ShopItem>(shopItemId);
      if(!shopItem) continue;
      auto item = data.getRow<Excel::Item>(shopItem->data().ItemId);
      if(!item || !item->data().Price || item->data().Price > reward->data().Price) continue;
      if(item->data().Price < purchasePrice)
      {
        purchaseItem = shopItem->data().ItemId; purchasePrice = item->data().Price; purchaseIndex = index;
      }
    }
    if(!purchaseItem) throw std::runtime_error("selected gil shop has no affordable source item");
    auto selectedItem = data.getRow<Excel::Item>(purchaseItem);
    if(!selectedItem || !selectedItem->data().StackMax)
      throw std::runtime_error("selected gil-shop item has no stack metadata");
    const auto purchaseQuantity = std::min<uint32_t>(selectedItem->data().StackMax,
                                                      reward->data().Price / purchasePrice);
    if(purchaseQuantity < 2 || purchaseQuantity > 99)
      throw std::runtime_error("selected gil-shop item lacks a bounded multi-quantity purchase");
    nlohmann::json output{{"version", 1}, {"profile", "sapphire-3.3"}, {"territory", 130},
      {"start_actor", 1001289}, {"shop", {{"layout_id", selected.layout}, {"base_id", selected.base},
        {"event_id", selected.event}, {"position", {selected.position.x, selected.position.y, selected.position.z}}}},
      {"sale", {{"item", 4551}, {"quantity", 1}, {"gil", reward->data().Price}}},
      {"purchase", {{"shop_id", selected.event}, {"index", purchaseIndex}, {"item", purchaseItem},
                    {"quantity", purchaseQuantity}, {"unit_gil", purchasePrice},
                    {"gil", purchasePrice * purchaseQuantity}}},
      {"route_length", bestLength}, {"route", best},
      {"navigation", {{"mesh", std::filesystem::absolute(std::filesystem::path(argv[2]) / "w1t1" / "w1t1.nav").generic_string()},
                       {"format", "TSET-v1"}, {"polyref_bits", sizeof(dtPolyRef) * 8}}}};
    std::ofstream file(argv[3]);
    if(!file || !(file << output.dump(2) << '\n')) throw std::runtime_error("cannot write shop catalog");
  }
  catch(const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
