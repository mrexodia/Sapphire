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
    auto starterLegs = data.getRow<Excel::Item>(3296);
    auto starterBody = data.getRow<Excel::Item>(2983);
    auto starterFeet = data.getRow<Excel::Item>(3750);
    if(!reward || !reward->data().Price) throw std::runtime_error("supported sale item has no gil value");
    if(!starterLegs || !starterLegs->data().Price)
      throw std::runtime_error("supported starter-leg liquidation has no gil value");
    if(!starterBody || !starterBody->data().Price)
      throw std::runtime_error("supported starter-body liquidation has no gil value");
    if(!starterFeet || !starterFeet->data().Price)
      throw std::runtime_error("supported starter-feet liquidation has no gil value");
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
    uint32_t equipmentItem = 0, equipmentPrice = std::numeric_limits<uint32_t>::max();
    uint32_t equipmentIndex = 0, equipmentSourceSlot = 0;
    struct EquipmentCandidate { uint32_t item, price, index, sourceSlot; };
    std::vector<EquipmentCandidate> equipmentCandidates;
    constexpr std::array<uint32_t, 5> starterItems{1601, 2983, 3520, 3296, 3750};
    for(uint32_t index = 0; index < 40; ++index)
    {
      const auto shopItemId = shop->data().Item[index];
      auto shopItem = data.getRow<Excel::ShopItem>(shopItemId);
      if(!shopItem) continue;
      auto item = data.getRow<Excel::Item>(shopItem->data().ItemId);
      if(item && item->data().Price && item->data().Price <= reward->data().Price * 4u &&
         item->data().StackMax == 1 && item->data().Slot > 0 && item->data().Slot <= 13 &&
         item->data().EquipLevel <= 1 && item->data().Class == 0 &&
         std::find(starterItems.begin(), starterItems.end(), shopItem->data().ItemId) == starterItems.end())
      {
        equipmentCandidates.push_back({static_cast<uint32_t>(shopItem->data().ItemId), item->data().Price, index,
                                       item->data().Slot});
        if(item->data().Price < equipmentPrice)
        {
          equipmentItem = shopItem->data().ItemId; equipmentPrice = item->data().Price;
          equipmentIndex = index; equipmentSourceSlot = item->data().Slot;
        }
      }
      if(!item || !item->data().Price || item->data().Price > reward->data().Price) continue;
      if(item->data().Price < purchasePrice)
      {
        purchaseItem = shopItem->data().ItemId; purchasePrice = item->data().Price; purchaseIndex = index;
      }
    }
    if(!purchaseItem) throw std::runtime_error("selected gil shop has no affordable source item");
    if(!equipmentItem || equipmentSourceSlot < 2)
      throw std::runtime_error("selected gil shop has no bounded later equipment purchase");
    EquipmentCandidate secondEquipment{};
    for(const auto& candidate : equipmentCandidates)
      if(candidate.sourceSlot != equipmentSourceSlot &&
         (!secondEquipment.item || candidate.price < secondEquipment.price ||
          (candidate.price == secondEquipment.price && candidate.item < secondEquipment.item)))
        secondEquipment = candidate;
    if(!secondEquipment.item || secondEquipment.sourceSlot < 2 ||
       secondEquipment.price > reward->data().Price * 2u)
      throw std::runtime_error("selected gil shop has no second affordable equipment slot");
    EquipmentCandidate thirdEquipment{};
    const auto thirdFunds = reward->data().Price * 2u - secondEquipment.price +
                            secondEquipment.price + starterLegs->data().Price;
    for(const auto& candidate : equipmentCandidates)
      if(candidate.sourceSlot != equipmentSourceSlot &&
         candidate.sourceSlot != secondEquipment.sourceSlot && candidate.price <= thirdFunds &&
         (!thirdEquipment.item || candidate.price < thirdEquipment.price ||
          (candidate.price == thirdEquipment.price && candidate.item < thirdEquipment.item)))
        thirdEquipment = candidate;
    if(!thirdEquipment.item || thirdEquipment.sourceSlot < 2)
      throw std::runtime_error("selected gil shop has no third affordable equipment slot");

    struct HeadCandidate
    {
      Candidate shop{}; uint32_t item{}, price{}, index{};
      double routeLength{std::numeric_limits<double>::infinity()};
      std::vector<std::array<float, 3>> route;
    } head;
    const auto headFunds = thirdFunds - thirdEquipment.price + starterBody->data().Price;
    for(const auto& candidate : candidates)
    {
      auto candidateShop = data.getRow<Excel::Shop>(candidate.event);
      if(!candidateShop) continue;
      for(uint32_t index = 0; index < 40; ++index)
      {
        auto shopItem = data.getRow<Excel::ShopItem>(candidateShop->data().Item[index]);
        if(!shopItem) continue;
        auto item = data.getRow<Excel::Item>(shopItem->data().ItemId);
        if(!item || !item->data().Price || item->data().Price > headFunds ||
           item->data().StackMax != 1 || item->data().Slot != 3 ||
           item->data().EquipLevel > 1 || item->data().Class != 0)
          continue;
        try
        {
          auto route = Sapphire::Testing::navigationRoute(*finder.getNavMesh(),
            {selected.position.x, selected.position.y, selected.position.z},
            {candidate.position.x, candidate.position.y, candidate.position.z});
          double length = 0;
          for(size_t i = 1; i < route.size(); ++i)
          {
            const auto& a = route[i - 1]; const auto& b = route[i];
            const double step = std::sqrt(std::pow(a[0]-b[0], 2) + std::pow(a[1]-b[1], 2) +
                                          std::pow(a[2]-b[2], 2));
            if(!std::isfinite(step) || step > 2)
              throw std::runtime_error("head-shop route contains unsupported jump");
            length += step;
          }
          const auto itemId = static_cast<uint32_t>(shopItem->data().ItemId);
          if(!head.item || item->data().Price < head.price ||
             (item->data().Price == head.price && length < head.routeLength) ||
             (item->data().Price == head.price && length == head.routeLength && itemId < head.item))
            head = {candidate, itemId, item->data().Price, index, length, std::move(route)};
        }
        catch(const std::exception&) { /* A partial corridor is never selected. */ }
      }
    }
    if(!head.item || head.route.empty() || !std::isfinite(head.routeLength) || head.routeLength > 500)
      throw std::runtime_error("no complete affordable route to a source-listed head shop");

    HeadCandidate ear;
    const auto earFunds = headFunds - head.price + starterFeet->data().Price;
    for(const auto& candidate : candidates)
    {
      auto candidateShop = data.getRow<Excel::Shop>(candidate.event);
      if(!candidateShop) continue;
      for(uint32_t index = 0; index < 40; ++index)
      {
        auto shopItem = data.getRow<Excel::ShopItem>(candidateShop->data().Item[index]);
        if(!shopItem) continue;
        auto item = data.getRow<Excel::Item>(shopItem->data().ItemId);
        if(!item || !item->data().Price || item->data().Price > earFunds ||
           item->data().StackMax != 1 || item->data().Slot != 9 ||
           item->data().EquipLevel > 1 || item->data().Class != 0)
          continue;
        try
        {
          auto route = Sapphire::Testing::navigationRoute(*finder.getNavMesh(),
            {head.shop.position.x, head.shop.position.y, head.shop.position.z},
            {candidate.position.x, candidate.position.y, candidate.position.z});
          double length = 0;
          for(size_t i = 1; i < route.size(); ++i)
          {
            const auto& a = route[i - 1]; const auto& b = route[i];
            const double step = std::sqrt(std::pow(a[0]-b[0], 2) + std::pow(a[1]-b[1], 2) +
                                          std::pow(a[2]-b[2], 2));
            if(!std::isfinite(step) || step > 2)
              throw std::runtime_error("ear-shop route contains unsupported jump");
            length += step;
          }
          const auto itemId = static_cast<uint32_t>(shopItem->data().ItemId);
          if(!ear.item || item->data().Price < ear.price ||
             (item->data().Price == ear.price && length < ear.routeLength) ||
             (item->data().Price == ear.price && length == ear.routeLength && itemId < ear.item))
            ear = {candidate, itemId, item->data().Price, index, length, std::move(route)};
        }
        catch(const std::exception&) { /* A partial corridor is never selected. */ }
      }
    }
    if(!ear.item || ear.route.empty() || !std::isfinite(ear.routeLength) || ear.routeLength > 500)
      throw std::runtime_error("no complete affordable route to a source-listed ear shop");

    HeadCandidate neck;
    const auto neckFunds = earFunds - ear.price + thirdEquipment.price + head.price + ear.price;
    for(const auto& candidate : candidates)
    {
      auto candidateShop = data.getRow<Excel::Shop>(candidate.event);
      if(!candidateShop) continue;
      for(uint32_t index = 0; index < 40; ++index)
      {
        auto shopItem = data.getRow<Excel::ShopItem>(candidateShop->data().Item[index]);
        if(!shopItem) continue;
        auto item = data.getRow<Excel::Item>(shopItem->data().ItemId);
        if(!item || !item->data().Price || item->data().Price > neckFunds ||
           item->data().StackMax != 1 || item->data().Slot != 10 ||
           item->data().EquipLevel > 1 || item->data().Class != 0)
          continue;
        try
        {
          auto route = Sapphire::Testing::navigationRoute(*finder.getNavMesh(),
            {ear.shop.position.x, ear.shop.position.y, ear.shop.position.z},
            {candidate.position.x, candidate.position.y, candidate.position.z});
          double length = 0;
          for(size_t i = 1; i < route.size(); ++i)
          {
            const auto& a = route[i - 1]; const auto& b = route[i];
            const double step = std::sqrt(std::pow(a[0]-b[0], 2) + std::pow(a[1]-b[1], 2) +
                                          std::pow(a[2]-b[2], 2));
            if(!std::isfinite(step) || step > 2)
              throw std::runtime_error("neck-shop route contains unsupported jump");
            length += step;
          }
          const auto itemId = static_cast<uint32_t>(shopItem->data().ItemId);
          if(!neck.item || item->data().Price < neck.price ||
             (item->data().Price == neck.price && length < neck.routeLength) ||
             (item->data().Price == neck.price && length == neck.routeLength && itemId < neck.item))
            neck = {candidate, itemId, item->data().Price, index, length, std::move(route)};
        }
        catch(const std::exception&) { /* A partial corridor is never selected. */ }
      }
    }
    if(!neck.item || neck.route.empty() || !std::isfinite(neck.routeLength) || neck.routeLength > 500)
      throw std::runtime_error("no complete affordable route to a source-listed neck shop");
    auto selectedItem = data.getRow<Excel::Item>(purchaseItem);
    if(!selectedItem || !selectedItem->data().StackMax)
      throw std::runtime_error("selected gil-shop item has no stack metadata");
    const auto purchaseQuantity = std::min<uint32_t>(selectedItem->data().StackMax,
                                                      reward->data().Price / purchasePrice);
    if(purchaseQuantity < 2 || purchaseQuantity > 99)
      throw std::runtime_error("selected gil-shop item lacks a bounded multi-quantity purchase");
    auto itemAction = data.getRow<Excel::ItemAction>(selectedItem->data().Action);
    if(!itemAction) throw std::runtime_error("selected gil-shop item has no source action metadata");
    nlohmann::json output{{"version", 1}, {"profile", "sapphire-3.3"}, {"territory", 130},
      {"start_actor", 1001289}, {"shop", {{"layout_id", selected.layout}, {"base_id", selected.base},
        {"event_id", selected.event}, {"position", {selected.position.x, selected.position.y, selected.position.z}}}},
      {"sale", {{"item", 4551}, {"quantity", 1}, {"gil", reward->data().Price}}},
      {"starter_liquidation", {{"item", 3296}, {"quantity", 1},
                                {"gil", starterLegs->data().Price}}},
      {"starter_body_liquidation", {{"item", 2983}, {"quantity", 1},
                                     {"gil", starterBody->data().Price}}},
      {"starter_feet_liquidation", {{"item", 3750}, {"quantity", 1},
                                     {"gil", starterFeet->data().Price}}},
      {"purchase", {{"shop_id", selected.event}, {"index", purchaseIndex}, {"item", purchaseItem},
                    {"quantity", purchaseQuantity}, {"unit_gil", purchasePrice},
                    {"gil", purchasePrice * purchaseQuantity},
                    {"item_action", {{"row", selectedItem->data().Action},
                                     {"type", itemAction->data().Action},
                                     {"arg", itemAction->data().Calcu0Arg[0]}}}}},
      {"equipment_purchase", {{"shop_id", selected.event}, {"index", equipmentIndex},
                              {"item", equipmentItem}, {"quantity", 1},
                              {"gil", equipmentPrice}, {"resale_gil", equipmentPrice},
                              {"source_slot", equipmentSourceSlot},
                              {"gear_slot", equipmentSourceSlot - 1}}},
      {"second_equipment_purchase", {{"shop_id", selected.event}, {"index", secondEquipment.index},
                                     {"item", secondEquipment.item}, {"quantity", 1},
                                     {"gil", secondEquipment.price}, {"resale_gil", secondEquipment.price},
                                     {"source_slot", secondEquipment.sourceSlot},
                                     {"gear_slot", secondEquipment.sourceSlot - 1}}},
      {"third_equipment_purchase", {{"shop_id", selected.event}, {"index", thirdEquipment.index},
                                    {"item", thirdEquipment.item}, {"quantity", 1},
                                    {"gil", thirdEquipment.price},
                                    {"source_slot", thirdEquipment.sourceSlot},
                                    {"gear_slot", thirdEquipment.sourceSlot - 1}}},
      {"head_purchase", {{"shop", {{"layout_id", head.shop.layout}, {"base_id", head.shop.base},
                                     {"event_id", head.shop.event},
                                     {"position", {head.shop.position.x, head.shop.position.y,
                                                    head.shop.position.z}}}},
                         {"index", head.index}, {"item", head.item}, {"quantity", 1},
                         {"gil", head.price}, {"source_slot", 3}, {"gear_slot", 2},
                         {"route_length", head.routeLength}, {"route", head.route}}},
      {"ear_purchase", {{"shop", {{"layout_id", ear.shop.layout}, {"base_id", ear.shop.base},
                                      {"event_id", ear.shop.event},
                                      {"position", {ear.shop.position.x, ear.shop.position.y,
                                                     ear.shop.position.z}}}},
                          {"index", ear.index}, {"item", ear.item}, {"quantity", 1},
                          {"gil", ear.price}, {"source_slot", 9}, {"gear_slot", 8},
                          {"route_length", ear.routeLength}, {"route", ear.route}}},
      {"neck_purchase", {{"shop", {{"layout_id", neck.shop.layout}, {"base_id", neck.shop.base},
                                       {"event_id", neck.shop.event},
                                       {"position", {neck.shop.position.x, neck.shop.position.y,
                                                      neck.shop.position.z}}}},
                           {"index", neck.index}, {"item", neck.item}, {"quantity", 1},
                           {"gil", neck.price}, {"source_slot", 10}, {"gear_slot", 9},
                           {"route_length", neck.routeLength}, {"route", neck.route}}},
      {"route_length", bestLength}, {"route", best},
      {"navigation", {{"mesh", std::filesystem::absolute(std::filesystem::path(argv[2]) / "w1t1" / "w1t1.nav").generic_string()},
                       {"format", "TSET-v1"}, {"polyref_bits", sizeof(dtPolyRef) * 8}}}};
    std::ofstream file(argv[3]);
    if(!file || !(file << output.dump(2) << '\n')) throw std::runtime_error("cannot write shop catalog");
  }
  catch(const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
